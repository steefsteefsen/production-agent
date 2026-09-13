"""FastAPI-Backend: startet Untersuchungen, streamt Knotenergebnisse (SSE), nimmt Freigaben an."""

from __future__ import annotations

import json
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langgraph.types import Command
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from production_agent.api.mes_router import router as mes_router
from production_agent.config import get_settings
from production_agent.graph.workflow import build_graph

settings = get_settings()
app = FastAPI(title="Production Agent PoC")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(mes_router)
graph = build_graph(checkpoint_path=settings.checkpoint_db_path)


class StartRequest(BaseModel):
    line_id: str


class ApprovalRequest(BaseModel):
    thread_id: str
    approved: bool
    comment: str = ""
    approved_action_titles: list[str] = []


@app.get("/investigations/stream")
async def stream_investigation(line_id: str = "L1") -> EventSourceResponse:
    """SSE-Stream: je Knoten ein Event {node, payload, trace}; stoppt am Freigabeknoten.

    Events:
    - event: start  → {"thread_id": "..."}
    - event: node   → {"node": "<name>", "payload": {...}, "trace": [...]}
    - event: interrupt → {"node": "approval_gate", "actions": [...], "thread_id": "..."}
    """
    thread_id = str(uuid.uuid4())
    cfg = {"configurable": {"thread_id": thread_id}}

    async def _generator():
        yield {"event": "start", "data": json.dumps({"thread_id": thread_id})}
        for update in graph.stream(
            {"line_id": line_id, "trace": []}, cfg, stream_mode="updates"
        ):
            for node, state_update in update.items():
                if node == "__interrupt__":
                    payload = state_update[0].value if state_update else {}
                    yield {
                        "event": "interrupt",
                        "data": json.dumps(
                            {"node": "approval_gate", "payload": payload, "thread_id": thread_id}
                        ),
                    }
                else:
                    trace = state_update.get("trace", []) if isinstance(state_update, dict) else []
                    yield {
                        "event": "node",
                        "data": json.dumps(
                            {"node": node, "payload": state_update, "trace": trace}
                        ),
                    }

    return EventSourceResponse(_generator())


@app.post("/investigations")
def start(req: StartRequest) -> dict:
    """Untersuchung starten (synchron); gibt thread_id und Interrupt-Payload zurück."""
    thread_id = str(uuid.uuid4())
    cfg = {"configurable": {"thread_id": thread_id}}
    result = graph.invoke({"line_id": req.line_id, "trace": []}, config=cfg)
    return {"thread_id": thread_id, "state": result, "interrupt": result.get("__interrupt__")}


@app.post("/investigations/approve")
def approve(req: ApprovalRequest) -> dict:
    cfg = {"configurable": {"thread_id": req.thread_id}}
    snapshot = graph.get_state(cfg)
    if not snapshot.next:
        raise HTTPException(
            status_code=409, detail="Kein wartender Freigabeknoten für diesen Thread"
        )
    result = graph.invoke(Command(resume=req.model_dump()), config=cfg)
    return {"thread_id": req.thread_id, "state": result}


@app.get("/health")
def health() -> dict:
    return {"ok": True, "model": settings.anthropic_model, "langfuse": settings.langfuse_enabled}
