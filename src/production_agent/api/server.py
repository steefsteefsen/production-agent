"""FastAPI-Backend: startet Untersuchungen, streamt Knotenergebnisse (SSE), nimmt Freigaben an."""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langgraph.types import Command
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from production_agent.api.mes_router import router as mes_router
from production_agent.config import get_settings
from production_agent.data.replay import case_for_event_id, score
from production_agent.graph.workflow import build_graph

DEMO_EVENT_ID = 360  # jüngstes Gold-Ereignis (STO-FOLIE); Default der geführten Demo


def _replay_case(event_id: int):
    """Replay-Fall (SIM_NOW, line_id, Gold-Wahrheit) für ein Ereignis – read-only, kein Leck an den
    Agenten (nur die Uhr wird gesetzt; die Gold-Zeile dient allein der Eval nach dem Lauf)."""
    conn = sqlite3.connect(f"file:{get_settings().mes_db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        return case_for_event_id(conn, event_id)
    finally:
        conn.close()


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
    # optional: nur für Replay-Fälle mit bekanntem Gold – ermöglicht die Eval NACH der Freigabe
    event_id: int | None = None


def _pace_seconds(delay_ms: int) -> float:
    """Demo-Takt in Sekunden, auf [0, 2] gedeckelt (0 = Produktivpfad, unverändert schnell)."""
    return max(0, min(delay_ms, 2000)) / 1000


def _post_run_eval(event_id: int | None, state: dict) -> dict | None:
    """Eval NACH der Freigabe (ADR-0002-konform, kein Leck während des Laufs).

    Vergleicht die Hypothese des Agenten mit der verborgenen Gold-Wahrheit über den kanonischen
    replay.score und zählt die belegten Maßnahmen (mit Beleg/rationale). Gibt None zurück, wenn
    kein event_id übergeben wurde oder der Fall keine Gold-Zeile hat (nichts raten)."""
    if event_id is None:
        return None
    case = _replay_case(event_id)
    if case is None or not case.truth:
        return None
    hypothesis = state.get("hypothesis") or {}
    impact = state.get("impact") or {}
    actions = state.get("actions") or []
    prediction = {
        "reason_code": hypothesis.get("reason_code"),
        "expected_downtime_min": impact.get("expected_downtime_min"),
    }
    scored = score(prediction, case.truth)
    supported = sum(1 for a in actions if isinstance(a, dict) and a.get("rationale"))
    return {
        "reason_hit": scored["reason_hit"],
        "reason_code_pred": hypothesis.get("reason_code"),
        "reason_code_gold": case.truth.get("reason_code"),
        "supported_actions": supported,
        "total_actions": len(actions),
    }


@app.get("/investigations/stream")
async def stream_investigation(
    line_id: str = "L1", event_id: int = DEMO_EVENT_ID, delay_ms: int = 0
) -> EventSourceResponse:
    """SSE-Stream: je Knoten ein Event {node, payload, trace}; stoppt am Freigabeknoten.

    event_id wählt den Replay-Fall (Default 360): daraus wird die Replay-Uhr SIM_NOW für diesen
    Lauf gesetzt (die MES-Werkzeuge lesen sie zur Laufzeit). Der Modus mock/live steckt im
    Backend-LLM_MODE und wird nur mitgeschickt, nicht hier gesetzt.

    delay_ms taktet die Knoten-Events optional für die geführte Demo (Default 0 = unverändert
    schnell); der Produktivpfad ist davon unberührt. Obergrenze 2000 ms je Knoten.

    Events:
    - event: start  → {"thread_id", "event_id", "sim_now", "line_id", "mode"}
    - event: node   → {"node": "<name>", "payload": {...}, "trace": [...]}
    - event: interrupt → {"node": "approval_gate", "payload": {...}, "thread_id": "..."}
    """
    pace = _pace_seconds(delay_ms)  # Demo-Takt, gedeckelt
    thread_id = str(uuid.uuid4())
    cfg = {"configurable": {"thread_id": thread_id}}
    case = _replay_case(event_id)
    run_line = case.line_id if case else line_id
    if case:
        # Replay-Uhr dieses Laufs; die direktimportierten MES-Tools lesen SIM_NOW zur Laufzeit.
        os.environ["SIM_NOW"] = case.now

    async def _generator():
        yield {
            "event": "start",
            "data": json.dumps(
                {
                    "thread_id": thread_id,
                    "event_id": event_id if case else None,
                    "sim_now": case.now if case else None,
                    "line_id": run_line,
                    "mode": settings.llm_mode,
                }
            ),
        }
        for update in graph.stream({"line_id": run_line, "trace": []}, cfg, stream_mode="updates"):
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
                        "data": json.dumps({"node": node, "payload": state_update, "trace": trace}),
                    }
                    if pace:
                        await asyncio.sleep(pace)  # geführte Demo: Knoten sichtbar takten

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
    # event_id nur für die Eval nach dem Lauf, nicht Teil des Resume-Werts (Verhalten unverändert)
    result = graph.invoke(Command(resume=req.model_dump(exclude={"event_id"})), config=cfg)
    response: dict = {"thread_id": req.thread_id, "state": result}
    ev = _post_run_eval(req.event_id, result if isinstance(result, dict) else {})
    if ev is not None:
        response["eval"] = ev
    return response


@app.get("/investigations/gold/{event_id}")
def gold_truth(event_id: int) -> dict:
    """Gold-Wahrheit eines Replay-Falls – NUR für die Eval nach dem Lauf (reason_hit-Vergleich).

    Kein Werkzeug des Agenten: Der Agent sieht das nie während der Untersuchung (ADR-0002); erst
    das Cockpit vergleicht seine Hypothese danach damit. Read-only.
    """
    case = _replay_case(event_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Ereignis {event_id} nicht gefunden")
    return {"event_id": event_id, **case.truth}


@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "model": settings.llm_model_main,
        "mode": settings.llm_mode,
        "langfuse": settings.langfuse_enabled,
    }
