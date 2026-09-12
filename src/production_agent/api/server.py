"""FastAPI-Backend: startet Untersuchungen, streamt Knotenergebnisse (SSE), nimmt Freigaben an."""

from __future__ import annotations

import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langgraph.types import Command
from pydantic import BaseModel

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
graph = build_graph(settings.checkpoint_db_path)


class StartRequest(BaseModel):
    line_id: str


class ApprovalRequest(BaseModel):
    thread_id: str
    approved: bool
    comment: str = ""
    approved_action_titles: list[str] = []


@app.post("/investigations")
def start(req: StartRequest) -> dict:
    thread_id = str(uuid.uuid4())
    cfg = {"configurable": {"thread_id": thread_id}}
    result = graph.invoke({"line_id": req.line_id, "trace": []}, config=cfg)
    return {"thread_id": thread_id, "state": result, "interrupt": result.get("__interrupt__")}


@app.post("/investigations/approve")
def approve(req: ApprovalRequest) -> dict:
    cfg = {"configurable": {"thread_id": req.thread_id}}
    snapshot = graph.get_state(cfg)
    if not snapshot.next:  # kein wartender Freigabeknoten für diesen Thread
        raise HTTPException(
            status_code=409, detail="Kein wartender Freigabeknoten für diesen Thread"
        )
    result = graph.invoke(Command(resume=req.model_dump()), config=cfg)
    return {"thread_id": req.thread_id, "state": result}


@app.get("/health")
def health() -> dict:
    return {"ok": True, "model": settings.anthropic_model, "langfuse": settings.langfuse_enabled}
