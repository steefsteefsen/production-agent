#!/usr/bin/env python3
"""Replay-Eval (WP6): der Graph läuft je Replay-Fall gegen die echten MES/RAG-Werkzeuge.

Bewusst minimal und ehrlich – der erste Berührungspunkt mit MLOps/AIOps, kein Drift-Monitoring,
kein Retraining. Die Entscheidungsbasis wird nicht erfunden, sondern aus der Historie
ausgeschnitten (ADR-0002): die n jüngsten Gold-Ereignisse sind die Testfälle, ihre Gold-Zeile
(Ursache, Dauer) ist die für den Agenten unsichtbare Wahrheit.

Standard: LLM_MODE=mock – deterministisches Mock-LLM ohne API-Schlüssel (kein Geld, keine
Netzverbindung, CI-tauglich). --live nutzt ChatAnthropic über die API (nur Stefan, manuell).

Deterministische Prüfungen je Fall (unabhängig von der LLM-Antwort):
  - Freigabeknoten (interrupt) erreicht,
  - keine forbidden-Maßnahme in der Freigabe-Payload,
  - Konfidenz <= Formel-Obergrenze (decisions.yaml konfidenz.formel),
  - Alarmflut -> RAG/Wissenszweig durchlaufen,
  - korrekte Werkzeug-/Knotenreihenfolge (linearer Graph, keine Verzweigung).

Schreibt evals/report.md (Tabelle je Fall, Trefferquote, Ø Dauerfehler, Konfusionsmatrix Ursache)
und pflegt evals/scenarios.json (die gewählte Fallauswahl, reproduzierbar).
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from langfuse_tracing import tracing_config  # noqa: E402

from production_agent.config import get_settings  # noqa: E402
from production_agent.data.replay import score, select_replay_cases  # noqa: E402
from production_agent.graph.workflow import build_graph  # noqa: E402
from production_agent.security.action_policy import classify  # noqa: E402

PER_CASE_USD = 0.15  # grobe Schätzung Opus je Replay-Fall (nur --live)

# Erwartete Knotenreihenfolge (decisions.yaml: „einfachster Graph: keine Verzweigung").
EXPECTED_NODE_ORDER = [
    "capture_status",
    "analyze_alarms",
    "retrieve_knowledge",
    "narrow_cause",
    "estimate_impact",
    "derive_actions",
]


def _decisions() -> dict[str, Any]:
    return yaml.safe_load((ROOT / "decisions.yaml").read_text(encoding="utf-8"))


@dataclass
class CaseResult:
    """Ergebnis eines einzelnen Replay-Falls: Vorhersage, Gold-Wahrheit und alle Prüfungen."""

    event_id: int
    line_id: str
    now: str
    reason_code: str | None
    gold_reason_code: str | None
    reason_hit: bool
    duration_abs_err_min: float
    confidence: float | None
    confidence_bound: float
    alarm_flood: bool
    checks: dict[str, bool] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return all(self.checks.values())


def _tool_order_from_trace(trace: list[str]) -> list[str]:
    """Aus dem menschenlesbaren Trace die durchlaufenen Knoten in Reihenfolge rekonstruieren.

    Jeder Knoten protokolliert eine Zeile, die mit seiner Nummer beginnt (1..6). Die Zuordnung
    Nummer -> Knotenname ist die feste lineare Trajektorie des Graphen.
    """
    num_to_node = {
        "1": "capture_status",
        "2": "analyze_alarms",
        "3": "retrieve_knowledge",
        "4": "narrow_cause",
        "5": "estimate_impact",
        "6": "derive_actions",
    }
    order: list[str] = []
    for line in trace:
        head = line.strip().split(" ", 1)[0]
        if head in num_to_node:
            order.append(num_to_node[head])
    return order


def _confidence_bound(hypo: dict[str, Any], knowledge: list[dict[str, Any]]) -> float:
    """Obergrenze der Konfidenz aus der Formel in decisions.yaml:

        0.5 * regeltreffer + 0.3 * beste_fallaehnlichkeit + 0.2 * ursachenanteil_gleiche_faelle

    Ehrlich: aus dem Eval-Kontext ist nur der letzte Term (Ursachenanteil unter den abgerufenen
    ähnlichen Vorfällen) sauber ableitbar. Die beiden anderen Terme (Regeltreffer, beste
    Fallähnlichkeit) liegen hier nicht als saubere Zahl vor; wir setzen sie konservativ auf ihr
    Maximum (1.0). Die Schranke ist damit eine echte Obergrenze: unterschreitet der Ursachenanteil
    1.0, sinkt die Schranke, und eine übertrieben hohe LLM-Konfidenz wird erkannt. Die Formel senkt
    die Konfidenz nie unter das, was die Evidenz hergibt – sie deckelt nur nach oben (Systemprompt:
    „Du erhöhst die berechnete Konfidenz nie").
    """
    incidents = [
        k for k in knowledge if isinstance(k, dict) and k.get("event_id") not in (None, "")
    ]
    reason = hypo.get("reason_code")
    if incidents and reason:
        same = sum(1 for i in incidents if i.get("reason_code") == reason)
        ursachenanteil = same / len(incidents)
    else:
        ursachenanteil = 1.0
    return round(0.5 * 1.0 + 0.3 * 1.0 + 0.2 * ursachenanteil, 3)


def run_case(
    event_id: int, line_id: str, now: str, truth: dict[str, Any], *, live: bool
) -> CaseResult:
    """Einen Replay-Fall durch den Graph laufen lassen und alle Prüfungen auswerten."""
    # llm=None: build_graph wählt anhand LLM_MODE das Mock- oder Live-LLM. --live setzt LLM_MODE
    # NICHT hier, sondern erwartet, dass der Aufrufer die Umgebung entsprechend vorbereitet hat;
    # der Standardlauf bleibt mock (kein API-Schlüssel nötig).
    graph = build_graph(tools=None, sim_now=now, llm=None, checkpoint_path=None)
    cfg = tracing_config({"configurable": {"thread_id": f"eval-{event_id}"}})
    result = graph.invoke({"line_id": line_id, "trace": []}, cfg)

    trace = result.get("trace", []) or []
    knowledge = result.get("knowledge", []) or []
    hypo = result.get("hypothesis", {}) or {}
    flood = bool(result.get("alarm_flood", False))

    interrupt = result.get("__interrupt__")
    payload = interrupt[0].value if interrupt else {}
    actions = payload.get("actions", []) or []

    # Prüfung 1: Freigabeknoten (interrupt) erreicht.
    interrupt_reached = bool(interrupt)

    # Prüfung 2: keine forbidden-Maßnahme in der Freigabe-Payload.
    no_forbidden = all(
        classify(f"{a.get('title', '')} {a.get('description', '')}").value != "forbidden"
        for a in actions
    )

    # Prüfung 3: Konfidenz <= Formel-Obergrenze.
    confidence = hypo.get("confidence")
    bound = _confidence_bound(hypo, knowledge)
    confidence_le_formel = confidence is None or float(confidence) <= bound + 1e-9

    # Prüfung 4: Wissenszweig (RAG + ähnliche Vorfälle) wurde durchlaufen – bei Alarmflut Pflicht,
    # aber laut decisions.yaml (immer_wissen_abrufen) ohnehin immer.
    tool_order = _tool_order_from_trace(trace)
    rag_reached = "retrieve_knowledge" in tool_order
    flood_implies_rag = (not flood) or rag_reached

    # Prüfung 5: korrekte Knoten-/Werkzeugreihenfolge (linear, keine Verzweigung).
    order_correct = tool_order == EXPECTED_NODE_ORDER

    sc = score(hypo, truth)

    return CaseResult(
        event_id=event_id,
        line_id=line_id,
        now=now,
        reason_code=hypo.get("reason_code"),
        gold_reason_code=truth.get("reason_code"),
        reason_hit=bool(sc["reason_hit"]),
        duration_abs_err_min=float(sc["duration_abs_err_min"]),
        confidence=float(confidence) if confidence is not None else None,
        confidence_bound=bound,
        alarm_flood=flood,
        checks={
            "interrupt_erreicht": interrupt_reached,
            "keine_forbidden_massnahme": no_forbidden,
            "konfidenz_le_formel": confidence_le_formel,
            "alarmflut_rag_zweig": flood_implies_rag,
            "werkzeugreihenfolge": order_correct,
        },
    )


def select_cases(conn: sqlite3.Connection, n: int, offset_min: int) -> list[Any]:
    """Replay-Fälle über replay.select_replay_cases wählen; min_history sinnvoll klein halten,
    damit auch bei kleiner Historie genug Fälle übrig bleiben."""
    total = conn.execute(
        "SELECT COUNT(*) FROM downtime_events_gold WHERE end_ts IS NOT NULL"
    ).fetchone()[0]
    # Genug Historie vor den Testfällen lassen, aber bei kleiner DB nicht alle Fälle wegschneiden.
    min_history = min(20, max(0, total - n))
    return select_replay_cases(conn, n=n, offset_min=offset_min, min_history=min_history)


def write_scenarios(cases: list[Any], path: Path) -> None:
    """Fallauswahl reproduzierbar festhalten (evals/scenarios.json)."""
    data = {
        "beschreibung": "Replay-Fallauswahl der WP6-Eval: n jüngste Gold-Ereignisse (ADR-0002).",
        "faelle": [
            {
                "event_id": c.event_id,
                "line_id": c.line_id,
                "sim_now": c.now,
                "gold_reason_code": c.truth.get("reason_code"),
                "gold_duration_min": c.truth.get("duration_min"),
            }
            for c in cases
        ],
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _confusion_matrix(results: list[CaseResult]) -> list[tuple[str, str, int]]:
    """Konfusionsmatrix Ursache: (gold_reason_code, predicted_reason_code) -> Anzahl."""
    counter: Counter[tuple[str, str]] = Counter()
    for r in results:
        gold = r.gold_reason_code or "(kein)"
        pred = r.reason_code or "(kein)"
        counter[(gold, pred)] += 1
    return [(g, p, n) for (g, p), n in sorted(counter.items())]


def build_report(results: list[CaseResult], *, live: bool) -> str:
    """Markdown-Bericht: Tabelle je Fall, Trefferquote, Ø Dauerfehler, Konfusionsmatrix."""
    n = len(results)
    hits = sum(1 for r in results if r.reason_hit)
    hit_rate = (hits / n) if n else 0.0
    avg_err = (sum(r.duration_abs_err_min for r in results) / n) if n else 0.0
    all_checks_ok = sum(1 for r in results if r.ok)

    mode = "live (ChatAnthropic)" if live else "mock (deterministisches Mock-LLM)"
    lines: list[str] = []
    lines.append("# Replay-Eval – Bericht")
    lines.append("")
    lines.append(
        "Erzeugt von `evals/run_evals.py` aus einem echten Graph-Lauf je Replay-Fall "
        f"(LLM-Modus: {mode}). Grundlage: ADR-0002 – Historie und aktueller Fall stammen aus "
        "derselben Verteilung; die Gold-Zeile ist die für den Agenten unsichtbare Wahrheit."
    )
    lines.append("")
    lines.append(
        "> Ehrlichkeitsgrenze: Der Simulator kennt seine eigenen Ursachen. Trefferquote und "
        "Dauerfehler sind eine **Obergrenze**, kein Feldwert. Dies ist MLOps-light "
        "(kein Drift-Monitoring, kein Retraining)."
    )
    lines.append("")
    lines.append("## Kennzahlen")
    lines.append("")
    lines.append(f"- Fälle: {n}")
    lines.append(f"- Ursachen-Trefferquote (reason_hit): {hit_rate:.0%} ({hits}/{n})")
    lines.append(f"- Ø absoluter Dauerfehler: {avg_err:.1f} min")
    lines.append(f"- Fälle mit allen deterministischen Prüfungen grün: {all_checks_ok}/{n}")
    lines.append("")
    lines.append("## Fälle")
    lines.append("")
    lines.append(
        "| event_id | Linie | gold | vorhergesagt | reason_hit | Dauerfehler (min) | "
        "Konfidenz | Schranke | Flut | Prüfungen |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for r in results:
        conf = f"{r.confidence:.2f}" if r.confidence is not None else "–"
        checks_ok = (
            "alle grün" if r.ok else "rot: " + ",".join(k for k, v in r.checks.items() if not v)
        )
        lines.append(
            f"| {r.event_id} | {r.line_id} | {r.gold_reason_code} | {r.reason_code} | "
            f"{'ja' if r.reason_hit else 'nein'} | {r.duration_abs_err_min:.1f} | {conf} | "
            f"{r.confidence_bound:.2f} | {'ja' if r.alarm_flood else 'nein'} | {checks_ok} |"
        )
    lines.append("")
    lines.append("## Deterministische Prüfungen (je Fall)")
    lines.append("")
    check_keys = [
        "interrupt_erreicht",
        "keine_forbidden_massnahme",
        "konfidenz_le_formel",
        "alarmflut_rag_zweig",
        "werkzeugreihenfolge",
    ]
    lines.append("| Prüfung | grün | von |")
    lines.append("|---|---|---|")
    for key in check_keys:
        ok = sum(1 for r in results if r.checks.get(key))
        lines.append(f"| {key} | {ok} | {n} |")
    lines.append("")
    lines.append("## Konfusionsmatrix Ursache (gold → vorhergesagt)")
    lines.append("")
    lines.append("| gold_reason_code | vorhergesagt | Anzahl |")
    lines.append("|---|---|---|")
    for gold, pred, cnt in _confusion_matrix(results):
        marker = " " if gold == pred else " *"
        lines.append(f"| {gold} | {pred}{marker} | {cnt} |")
    lines.append("")
    lines.append("*) Zeilen mit Stern: Fehlklassifikation (gold ≠ vorhergesagt).")
    lines.append("")
    return "\n".join(lines)


def run_eval(*, live: bool = False) -> tuple[list[CaseResult], str]:
    """Vollständige Eval ausführen: Fälle wählen, je Fall den Graph laufen lassen, Bericht bauen."""
    dec = _decisions()
    sim = dec.get("simulation", {})
    n = int(sim.get("replay_testfaelle", 10))
    offset_min = int(sim.get("replay_uhr_offset_min", 5))

    settings = get_settings()
    conn = sqlite3.connect(settings.mes_db_path)
    conn.row_factory = sqlite3.Row
    try:
        cases = select_cases(conn, n=n, offset_min=offset_min)
    finally:
        conn.close()

    write_scenarios(cases, ROOT / "evals" / "scenarios.json")

    results = [run_case(c.event_id, c.line_id, c.now, c.truth, live=live) for c in cases]
    report = build_report(results, live=live)
    return results, report


def estimate() -> tuple[int, float]:
    dec = _decisions()
    n = dec.get("simulation", {}).get("replay_testfaelle", 10)
    return n, round(n * PER_CASE_USD, 2)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Replay-Eval (Standard: mock, kostenlos, offline)")
    ap.add_argument(
        "--live", action="store_true", help="kostenpflichtigen Live-Lauf über die API (nur Stefan)"
    )
    ap.add_argument("--estimate-only", action="store_true", help="nur die Kostenschätzung ausgeben")
    args = ap.parse_args(argv)

    if args.estimate_only:
        n, cost = estimate()
        print(f"Replay-Eval: {n} Fälle × Opus ≈ {cost} USD (Schätzung).")
        return 0

    settings = get_settings()
    if not Path(settings.mes_db_path).exists():
        print(
            f"Keine Gold-Datenbank unter {settings.mes_db_path} – erst den Simulator laufen lassen:"
            " python -m production_agent.data.simulator",
            file=sys.stderr,
        )
        return 1

    if args.live and not (ROOT / ".env").exists():
        print("Kein .env mit ANTHROPIC_API_KEY – Live-Lauf nicht möglich.", file=sys.stderr)
        return 1

    results, report = run_eval(live=args.live)
    (ROOT / "evals" / "report.md").write_text(report, encoding="utf-8")

    n = len(results)
    hits = sum(1 for r in results if r.reason_hit)
    all_ok = sum(1 for r in results if r.ok)
    print(
        f"Replay-Eval fertig: {n} Fälle, Trefferquote {hits}/{n}, alle Prüfungen grün {all_ok}/{n}."
    )
    print("Bericht: evals/report.md · Fallauswahl: evals/scenarios.json")

    # Rote deterministische Prüfungen als Warnung melden (nicht Exit-blockierend – der Bericht
    # entsteht immer, damit die Zahlen sichtbar sind und relativiert werden können).
    reds = defaultdict(int)
    for r in results:
        for k, v in r.checks.items():
            if not v:
                reds[k] += 1
    if reds:
        print("Achtung, rote Prüfungen:", dict(reds), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
