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

from production_agent import observability as obs
from production_agent.api.mes_router import router as mes_router
from production_agent.config import get_settings
from production_agent.data.replay import case_for_event_id, score
from production_agent.graph.workflow import build_graph


def _top_codes(alarms: list) -> list[str]:
    """Häufigste Alarmcodes (wie retrieve_knowledge sie als Suchquery nutzt)."""
    from collections import Counter

    codes = [a.get("alarm_code") for a in alarms if isinstance(a, dict) and a.get("alarm_code")]
    return [c for c, _ in Counter(codes).most_common(3)]


def _observe_node(node: str, upd: dict) -> None:
    """Echte Werkzeugaufrufe/Guard-Entscheidungen aus dem Knoten-Ergebnis in die Live-Sicht.

    Aus dem tatsächlichen State abgeleitet (kein Eingriff in die Tool-Module); die Werte
    (Alarmzahl, Vorfall-IDs, Judge-Urteile) sind real aus diesem Lauf."""
    if not isinstance(upd, dict):
        return
    if node == "capture_status":
        eq = upd.get("line_status", {})
        n = len(eq.get("equipment", [])) if isinstance(eq, dict) else 0
        obs.record_tool_call("mes", "get_line_status", {"line_id": "L1"}, {"equipment": n})
    elif node == "analyze_alarms":
        alarms = upd.get("alarms", []) or []
        obs.record_tool_call(
            "mes",
            "get_active_alarms",
            {"line_id": "L1", "window_min": 30},
            {"alarm_count": len(alarms), "flood_detected": bool(upd.get("alarm_flood"))},
        )
    elif node == "retrieve_knowledge":
        know = upd.get("knowledge", []) or []
        docs = [k for k in know if isinstance(k, dict) and not k.get("event_id")]
        inc = [str(k.get("event_id")) for k in know if isinstance(k, dict) and k.get("event_id")]
        top = docs[0].get("doc") if docs else None
        obs.record_tool_call(
            "maintenance_docs", "search", {"query": "Störungsbild"}, {"hits": len(docs), "top": top}
        )
        obs.record_tool_call("mes", "find_similar_incidents", {"limit": 5}, {"incidents": inc[:5]})
    elif node == "estimate_impact":
        imp = upd.get("impact", {}) or {}
        obs.record_tool_call("mes", "estimate_impact", {"line_id": "L1"}, imp)
    elif node == "check_evidence":
        for jr in upd.get("judge_results", []) or []:
            v = bool(jr.get("verified"))
            title = jr.get("title", "")
            obs.record_security("judge", v, f"Maßnahme '{title}' gegen Beleg geprüft: verified={v}")


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
# Demo-Default: die laufende Anwendung nutzt den ECHTEN MCP-Protokollpfad (fastmcp.Client über
# stdio), nicht den In-Process-Import. `make run-api` belegt so OHNE jede Variable „≥1 MCP-Server"
# im Beweisbetrieb (Log „Starting MCP server ... stdio"). Nur ein ausdrückliches MCP_VIA_PROTOCOL=0
# schaltet auf den schnellen, deterministischen In-Process-Pfad zurück (Tests/CI, die keine
# stdio-Subprozesse starten wollen). Ergebnis identisch, nur der Aufrufpfad unterscheidet sich
# (siehe build_graph-Docstring, ADR-0005). e2e_replay ist unberührt (nutzt settings-Default).
_demo_use_mcp = os.getenv("MCP_VIA_PROTOCOL", "1").strip().lower() not in ("0", "false", "no", "")
graph = build_graph(checkpoint_path=settings.checkpoint_db_path, use_mcp=_demo_use_mcp)


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
    line_id: str = "L1",
    event_id: int = DEMO_EVENT_ID,
    delay_ms: int = 0,
    tamper_evidence: bool = False,
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
    # demo_tamper nur für die geführte Demo (Beleg-Prüfung sichtbar ablehnen lassen); Default aus
    cfg = {"configurable": {"thread_id": thread_id, "demo_tamper": tamper_evidence}}
    case = _replay_case(event_id)
    run_line = case.line_id if case else line_id
    if case:
        # Replay-Uhr dieses Laufs; die direktimportierten MES-Tools lesen SIM_NOW zur Laufzeit.
        os.environ["SIM_NOW"] = case.now

    obs.reset()  # Live-Sicht (MCP/Sicherheit) für diesen Lauf leeren
    _record_guard_selftest()  # echte sql_guard-Entscheidungen (Allowlist-Treffer + Testblock)

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
                    _observe_node(node, state_update)  # echte Werkzeug-/Guard-Sicht mitschreiben
                    trace = state_update.get("trace", []) if isinstance(state_update, dict) else []
                    yield {
                        "event": "node",
                        "data": json.dumps({"node": node, "payload": state_update, "trace": trace}),
                    }
                    if pace:
                        await asyncio.sleep(pace)  # geführte Demo: Knoten sichtbar takten

    return EventSourceResponse(_generator())


def _record_guard_selftest() -> None:
    """Zwei ECHTE sql_guard-Auswertungen für die Sicherheit-Sicht: ein erlaubter SELECT auf der
    Allowlist und ein blockierter DROP (Testfall). Der Guard entscheidet real, nichts wird fingiert;
    dazu der Hinweis, dass injection_guard alle Werkzeugergebnisse kapselt."""
    from production_agent.security.sql_guard import SqlGuardError, validate_query

    try:
        validate_query("SELECT reason_code FROM downtime_events_gold LIMIT 1")
        obs.record_security("sql_guard", True, "SELECT auf downtime_events_gold erlaubt (Allow)")
    except SqlGuardError as e:  # pragma: no cover - Allowlist-Treffer erwartet
        obs.record_security("sql_guard", False, f"SELECT unerwartet blockiert: {e}")
    try:
        validate_query("DROP TABLE downtime_events_gold")
        obs.record_security("sql_guard", True, "DROP unerwartet erlaubt")  # pragma: no cover
    except SqlGuardError:
        obs.record_security("sql_guard", False, "DROP TABLE blockiert (Testfall, nicht Allowlist)")
    obs.record_security(
        "injection_guard", True, "Werkzeugergebnisse als Daten gekapselt (sanitize_tool_result)"
    )


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


# --- Live-Sicht (MCP-/Sicherheit-Tab): echte Aufrufe/Guard-Entscheidungen des jüngsten Laufs ---
@app.get("/observability")
def observability() -> dict:
    return obs.snapshot()


@app.get("/mcp/servers")
async def mcp_servers() -> dict:
    """Server + Werkzeuge aus der echten MCP-Definition (introspektiert, nicht hartkodiert)."""
    from production_agent.mcp import mes_server, rag_server

    async def _tools(srv) -> list[dict]:
        items = await srv.mcp._list_tools()
        return [
            {"name": t.name, "desc": (getattr(t, "description", "") or "").split("\n")[0].strip()}
            for t in items
        ]

    return {
        "servers": [
            {
                "name": "mes",
                "desc": "Zugriff auf Linienstatus, Alarme und Produktionsplan – schreibgeschützt.",
                "tools": await _tools(mes_server),
            },
            {
                "name": "maintenance_docs",
                "desc": "Durchsucht Wartungsdokumente – BM25 + Vektorsuche, RRF-fusioniert.",
                "tools": await _tools(rag_server),
            },
        ]
    }


# --- Wissen / RAG-Tab ---
@app.get("/knowledge/documents")
def knowledge_documents() -> dict:
    from production_agent.mcp.rag_server import document_inventory

    return document_inventory()


class DocRequest(BaseModel):
    text: str
    source: str = "rueckkopplung"


@app.post("/knowledge/documents")
def knowledge_ingest(req: DocRequest) -> dict:
    """Freigegebenen Rückkopplungstext in den RAG-Bestand einspeisen (Phase 2c, im nächsten Suchlauf
    auffindbar)."""
    from production_agent.mcp.rag_server import add_document

    try:
        chunk = add_document(req.text, req.source)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return {"ingested": chunk}


@app.get("/knowledge/search")
def knowledge_search(q: str, top_k: int = 5) -> dict:
    """Suchlauf mit rrf_rank (RAG-Tab): zeigt Fusionsrang statt nur BM25."""
    from production_agent.mcp.rag_server import search_hits

    hits = search_hits(q, top_k)
    return {"query": q, "code_match": bool(hits and hits[0].get("code_match")), "hits": hits}


# --- Rückkopplung: Rohtext → strukturierter Doku-Eintrag (Haiku 4.5) ---
class FeedbackRequest(BaseModel):
    raw: str
    reason_code: str = ""


@app.post("/investigations/feedback/suggest")
def feedback_suggest(req: FeedbackRequest) -> dict:
    """Macht aus dem Bediener-Rohtext einen strukturierten Wartungseintrag. Verändert NICHTS – der
    Vorschlag wird erst nach dem separaten Übernehmen-Klick eingespeist. LLM_MODE=mock liefert einen
    deterministischen Vorschlag (Tests/Demo, keine Kosten); live nutzt Haiku 4.5."""
    raw = (req.raw or "").strip()
    if not raw:
        raise HTTPException(status_code=422, detail="Kein Rohtext übergeben")
    if settings.llm_mode == "mock":
        return {"raw": raw, "suggestion": _mock_completion(raw, req.reason_code), "model": "mock"}
    return {
        "raw": raw,
        "suggestion": haiku_complete(raw, req.reason_code),
        "model": settings.llm_model_judge,
    }


def _mock_completion(raw: str, reason_code: str) -> str:
    """Deterministischer Vorschlag ohne API (Tests/Demo)."""
    rc = f" ({reason_code})" if reason_code else ""
    return (
        f"Ereignis{rc}: {raw}. "
        "Ursache: vor Ort bestätigt. "
        "Maßnahme: nach dokumentiertem Vorgehen behoben, Station geprüft. "
        "Wiederanlauf: kontrolliert über Execute-Schritt, keine Auffälligkeiten."
    )


_FEWSHOT = (
    "Beispiel 1 (Vorfall #358): 'Folienbahn lief schräg in die Siegelstation ein, Einspannung an "
    "Station 3 gelockert. Rolle neu eingespannt, Andruckrolle nachjustiert. Wiederanlauf nach ca. "
    "11 min.'\n"
    "Beispiel 2 (Vorfall #356): 'Station 3 quittiert, Bediener bestätigt Einspannung, Linie "
    "aus Held-Zustand über Execute-Schritt kontrolliert angefahren.'"
)


def haiku_complete(raw: str, reason_code: str) -> str:
    """EIN echter Haiku-4.5-Aufruf: Rohtext → Eintrag im Stil der Wartungsdokumente (#358/#356)."""
    from langchain_anthropic import ChatAnthropic
    from langchain_core.messages import HumanMessage, SystemMessage

    key = settings.anthropic_api_key.get_secret_value()
    llm = ChatAnthropic(model=settings.llm_model_judge, api_key=key, max_tokens=300)
    sys = (
        "Du hilfst einem Instandhalter, seine stichwortartige Rückmeldung zu einem behobenen "
        "Störungsfall in einen vollständigen, sachlichen Eintrag im Stil der bestehenden "
        "Dokumente zu bringen (Ereignis, Ursache, Maßnahme, Wiederanlauf). Nur der Eintrag, "
        "kein Vorspann. Erfinde keine Zahlen, die nicht genannt wurden.\n" + _FEWSHOT
    )
    hint = f"\nVermutete Ursachenklasse: {reason_code}" if reason_code else ""
    msg = f"Rohtext des Bedieners: {raw}{hint}\n\nStrukturierter Eintrag:"
    resp = llm.invoke([SystemMessage(content=sys), HumanMessage(content=msg)])
    return (resp.content if isinstance(resp.content, str) else str(resp.content)).strip()


# --- Konfiguration-Tab: echte Werte lesen/schreiben (runtime.yaml-Override, wie Ops-Cockpit) ---
@app.get("/api/config")
def api_config_get() -> dict:
    import yaml

    from production_agent.config import RUNTIME_YAML, runtime_value

    decisions = yaml.safe_load((_root() / "decisions.yaml").read_text(encoding="utf-8")) or {}
    konf = (decisions.get("konfidenz") or {}).get("schwelle_empfehlung", 0.60)
    vier = (decisions.get("freigabe") or {}).get("vier_augen_ab_kosten_eur", 5000)
    flut = (decisions.get("ereignis") or {}).get("alarmflut_alarme", 10)
    thr = runtime_value("konfidenz.schwelle_empfehlung", konf)
    return {
        "konfidenzschwelle": {"value": thr, "default": konf, "min": 0.0, "max": 1.0, "step": 0.05},
        "vier_augen_eur": {"value": vier, "min": 0, "max": 10000, "step": 500},
        "alarmflut": {"value": flut, "min": 1, "max": 30, "step": 1},
        "mcp_via_protocol": os.getenv("MCP_VIA_PROTOCOL", "1").strip().lower()
        not in ("0", "false", "no", ""),
        "langfuse": settings.langfuse_enabled,
        "drift": abs(float(thr) - float(konf)) > 1e-9,
        "runtime_path": str(RUNTIME_YAML),
    }


class ConfigPut(BaseModel):
    field: str
    value: float


@app.put("/api/config")
def api_config_put(req: ConfigPut) -> dict:
    """Schwellenwert in config/runtime.yaml schreiben – wirkt sofort (frisch gelesen)."""
    import yaml

    from production_agent.config import RUNTIME_YAML

    # Nur konfidenz.schwelle_empfehlung liest der Graph heute zur Laufzeit (derive_actions);
    # die anderen werden persistiert und angezeigt, wirken aber (noch) nicht im Ablauf.
    allowed = {
        "konfidenz.schwelle_empfehlung",
        "freigabe.vier_augen_ab_kosten_eur",
        "ereignis.alarmflut_alarme",
    }
    if req.field not in allowed:
        raise HTTPException(status_code=422, detail=f"Feld {req.field} nicht konfigurierbar")
    data = {}
    if RUNTIME_YAML.exists():
        data = yaml.safe_load(RUNTIME_YAML.read_text(encoding="utf-8")) or {}
    top, sub = req.field.split(".", 1)
    data.setdefault(top, {})[sub] = req.value
    RUNTIME_YAML.parent.mkdir(parents=True, exist_ok=True)
    RUNTIME_YAML.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return {"saved": {req.field: req.value}}


def _root():
    from pathlib import Path

    return Path(__file__).resolve().parents[3]
