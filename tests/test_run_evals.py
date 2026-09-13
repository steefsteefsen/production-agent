"""Tests für die WP6-Replay-Eval (evals/run_evals.py).

Jede neue Funktion hat einen Verifikationstest (tut sie das Richtige) und einen Falsifikationstest
(ein eingebauter Fehler macht ihn rot). Fixtures small_db/replay_env aus tests/conftest.py.
Alles im Mock-Modus – keine API, keine Netzverbindung.
"""

from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
EVALS = ROOT / "evals"
if str(EVALS) not in sys.path:
    sys.path.insert(0, str(EVALS))


def _load_run_evals():
    """evals/run_evals.py als Modul laden (liegt nicht im Paketpfad)."""
    spec = importlib.util.spec_from_file_location("run_evals", EVALS / "run_evals.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["run_evals"] = mod  # dataclass-Introspektion braucht das Modul in sys.modules
    spec.loader.exec_module(mod)
    return mod


re_mod = _load_run_evals()


# ---------------------------------------------------------------------------
# _tool_order_from_trace
# ---------------------------------------------------------------------------


def test_tool_order_from_trace_verifikation():
    """Verifikation: aus dem nummerierten Trace entsteht die lineare Knotenreihenfolge."""
    trace = [
        "1 Linienstatus und Produktionsplan erfasst",
        "2 Alarme analysiert (5), Alarmflut=False",
        "3 Wissen abgerufen: 2 Dokumente, 3 ähnliche Vorfälle",
        "4 Hypothese: STO-FOLIE (Konfidenz 0.80, Stillstand ~25 min)",
        "5 Wirkung geschätzt: 25.0 min Stillstand",
        "6 Maßnahmen abgeleitet, 2 mit Vorfall-ID belegt",
    ]
    assert re_mod._tool_order_from_trace(trace) == re_mod.EXPECTED_NODE_ORDER


def test_tool_order_from_trace_falsification():
    """Falsifikation: eine vertauschte Reihenfolge im Trace darf NICHT die Referenz ergeben."""
    trace = [
        "2 Alarme analysiert",
        "1 Linienstatus erfasst",
        "3 Wissen abgerufen",
    ]
    order = re_mod._tool_order_from_trace(trace)
    assert order != re_mod.EXPECTED_NODE_ORDER
    assert order[0] == "analyze_alarms"  # spiegelt die (falsche) Trace-Reihenfolge


# ---------------------------------------------------------------------------
# _confidence_bound
# ---------------------------------------------------------------------------


def test_confidence_bound_voller_ursachenanteil_verifikation():
    """Verifikation: teilen alle Vorfälle die Ursache, ist die Obergrenze 1.0 (0.5+0.3+0.2·1)."""
    hypo = {"reason_code": "STO-FOLIE"}
    knowledge = [
        {"event_id": 1, "reason_code": "STO-FOLIE"},
        {"event_id": 2, "reason_code": "STO-FOLIE"},
    ]
    assert re_mod._confidence_bound(hypo, knowledge) == pytest.approx(1.0)


def test_confidence_bound_sinkt_bei_uneinigkeit_falsification():
    """Falsifikation: teilt nur die Hälfte der Vorfälle die Ursache, MUSS die Schranke < 1.0 sein
    (0.5+0.3+0.2·0.5 = 0.9) – bliebe sie 1.0, wäre der Ursachenanteil-Term wirkungslos."""
    hypo = {"reason_code": "STO-FOLIE"}
    knowledge = [
        {"event_id": 1, "reason_code": "STO-FOLIE"},
        {"event_id": 2, "reason_code": "MAT-LEER"},
    ]
    bound = re_mod._confidence_bound(hypo, knowledge)
    assert bound == pytest.approx(0.9)
    assert bound < 1.0


# ---------------------------------------------------------------------------
# _confusion_matrix
# ---------------------------------------------------------------------------


def _mk_result(event_id, gold, pred, reason_hit=None):
    return re_mod.CaseResult(
        event_id=event_id,
        line_id="L1",
        now="2026-01-01 00:00:00",
        reason_code=pred,
        gold_reason_code=gold,
        reason_hit=(gold == pred) if reason_hit is None else reason_hit,
        duration_abs_err_min=1.0,
        confidence=0.8,
        confidence_bound=1.0,
        alarm_flood=False,
        checks={"interrupt_erreicht": True},
    )


def test_confusion_matrix_verifikation():
    """Verifikation: die Matrix zählt (gold, vorhergesagt)-Paare korrekt."""
    results = [
        _mk_result(1, "STO-FOLIE", "STO-FOLIE"),
        _mk_result(2, "STO-FOLIE", "STO-FOLIE"),
        _mk_result(3, "MAT-LEER", "STO-FOLIE"),
    ]
    matrix = dict(((g, p), n) for g, p, n in re_mod._confusion_matrix(results))
    assert matrix[("STO-FOLIE", "STO-FOLIE")] == 2
    assert matrix[("MAT-LEER", "STO-FOLIE")] == 1


def test_confusion_matrix_falsification():
    """Falsifikation: eine Fehlklassifikation darf NICHT in die Diagonale gezählt werden."""
    results = [_mk_result(1, "MAT-LEER", "STO-FOLIE")]
    matrix = dict(((g, p), n) for g, p, n in re_mod._confusion_matrix(results))
    assert ("MAT-LEER", "MAT-LEER") not in matrix  # kein Treffer erfunden


# ---------------------------------------------------------------------------
# build_report
# ---------------------------------------------------------------------------


def test_build_report_enthaelt_kennzahlen_verifikation():
    """Verifikation: der Bericht nennt Trefferquote, Ø Dauerfehler und Konfusionsmatrix."""
    results = [
        _mk_result(1, "STO-FOLIE", "STO-FOLIE"),
        _mk_result(2, "MAT-LEER", "STO-FOLIE"),  # Fehlklassifikation
    ]
    report = re_mod.build_report(results, live=False)
    assert "Trefferquote" in report
    assert "Ø absoluter Dauerfehler" in report
    assert "Konfusionsmatrix" in report
    assert "50%" in report  # 1 von 2 getroffen


def test_build_report_nicht_leer_falsification():
    """Falsifikation: auch bei null Fällen entsteht ein nicht-leerer, wohlgeformter Bericht
    (leerer Bericht wäre ein Fehler – das Kern-Artefakt darf nie leer sein)."""
    report = re_mod.build_report([], live=False)
    assert report.strip()
    assert "# Replay-Eval" in report


# ---------------------------------------------------------------------------
# run_case / run_eval gegen small_db (echter Graph-Lauf, Mock-LLM)
# ---------------------------------------------------------------------------


def test_run_case_gegen_small_db_verifikation(small_db, monkeypatch):
    """Verifikation: ein echter Fall aus small_db läuft durch und besteht alle deterministischen
    Prüfungen (Freigabeknoten, Werkzeugreihenfolge, Konfidenz-Schranke). reason_hit ist bewusst
    NICHT Teil der Zusicherung eines Einzelfalls – nicht jeder Fall hat historische Vorfälle
    (dann STO-UNBEKANNT), das ist ehrliches Verhalten; die Trefferquote wird aggregiert bewertet."""
    from production_agent.config import get_settings

    monkeypatch.setenv("MES_DB_PATH", str(small_db))
    monkeypatch.setenv("LLM_MODE", "mock")
    monkeypatch.setenv("AUDIT_LOG_PATH", str(small_db.parent / "audit.jsonl"))
    get_settings.cache_clear()

    conn = sqlite3.connect(small_db)
    conn.row_factory = sqlite3.Row
    case = re_mod.select_cases(conn, n=1, offset_min=5)[0]
    conn.close()

    res = re_mod.run_case(case.event_id, case.line_id, case.now, case.truth, live=False)
    assert res.checks["interrupt_erreicht"] is True
    assert res.checks["werkzeugreihenfolge"] is True
    assert res.checks["konfidenz_le_formel"] is True
    get_settings.cache_clear()


def test_run_eval_schreibt_report_und_scenarios_verifikation(small_db, monkeypatch, tmp_path):
    """Verifikation: run_eval liefert Ergebnisse und einen nicht-leeren Bericht, main() schreibt
    report.md und scenarios.json."""
    from production_agent.config import get_settings

    monkeypatch.setenv("MES_DB_PATH", str(small_db))
    monkeypatch.setenv("LLM_MODE", "mock")
    monkeypatch.setenv("AUDIT_LOG_PATH", str(small_db.parent / "audit.jsonl"))
    get_settings.cache_clear()

    results, report = re_mod.run_eval(live=False)
    assert len(results) >= 1
    assert "Trefferquote" in report
    # scenarios.json wurde in run_eval geschrieben und ist wohlgeformt
    import json

    scen = json.loads((re_mod.ROOT / "evals" / "scenarios.json").read_text(encoding="utf-8"))
    assert scen["faelle"]
    assert all("event_id" in f and "sim_now" in f for f in scen["faelle"])
    get_settings.cache_clear()


def test_run_eval_konfidenz_le_formel_falsification(small_db, monkeypatch):
    """Falsifikation der Konfidenz-Prüfung: hebt man die Schranke künstlich unter die
    LLM-Konfidenz (0.8), MUSS die Prüfung konfidenz_le_formel rot werden – sonst prüft sie nichts."""
    from production_agent.config import get_settings

    monkeypatch.setenv("MES_DB_PATH", str(small_db))
    monkeypatch.setenv("LLM_MODE", "mock")
    monkeypatch.setenv("AUDIT_LOG_PATH", str(small_db.parent / "audit.jsonl"))
    get_settings.cache_clear()

    # Schranke künstlich auf 0.5 deckeln (< Mock-Konfidenz 0.8)
    monkeypatch.setattr(re_mod, "_confidence_bound", lambda hypo, knowledge: 0.5)

    conn = sqlite3.connect(small_db)
    conn.row_factory = sqlite3.Row
    case = re_mod.select_cases(conn, n=1, offset_min=5)[0]
    conn.close()

    res = re_mod.run_case(case.event_id, case.line_id, case.now, case.truth, live=False)
    assert res.checks["konfidenz_le_formel"] is False
    get_settings.cache_clear()
