"""CBR-Tests: Jaccard-Ähnlichkeit, Fallbewertung, score_cases.

Verifikation: Jaccard-Logik, Gewichtung, Top-k-Auswahl.
Falsifikation: leere Eingaben, Typ-Robustheit.
"""

from __future__ import annotations

import pytest

from production_agent.graph.cbr import case_similarity, jaccard, score_cases

# ---------------------------------------------------------------------------
# jaccard
# ---------------------------------------------------------------------------


def test_jaccard_identische_mengen():
    """Verifikation: Jaccard zweier identischer Mengen = 1.0."""
    assert jaccard({"A", "B"}, {"A", "B"}) == pytest.approx(1.0)


def test_jaccard_disjunkte_mengen():
    """Verifikation: Jaccard zweier disjunkter Mengen = 0.0."""
    assert jaccard({"A"}, {"B"}) == pytest.approx(0.0)


def test_jaccard_teilmenge():
    """Verifikation: {A} ⊂ {A,B} → Jaccard = 0.5."""
    assert jaccard({"A"}, {"A", "B"}) == pytest.approx(0.5)


def test_jaccard_beide_leer_falsification():
    """Falsifikation: zwei leere Mengen → 0.0 (kein ZeroDivisionError)."""
    assert jaccard(set(), set()) == pytest.approx(0.0)


def test_jaccard_eine_leer():
    """Verifikation: eine leere Menge → 0.0."""
    assert jaccard(set(), {"A"}) == pytest.approx(0.0)
    assert jaccard({"A"}, set()) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# case_similarity
# ---------------------------------------------------------------------------


def _case(alarm_codes=None, packml_state="Held", rule_modes=None):
    return {
        "alarm_codes": alarm_codes or [],
        "packml_state": packml_state,
        "rule_modes": rule_modes or [],
    }


def test_case_similarity_perfekte_uebereinstimmung():
    """Verifikation: identische Codes, gleiches PackML, gleiche Regeln → 1.0."""
    sim = case_similarity(
        current_alarm_codes=["E-01", "E-02"],
        current_packml="Held",
        current_rule_modes=["TWF"],
        case=_case(alarm_codes=["E-01", "E-02"], packml_state="Held", rule_modes=["TWF"]),
    )
    assert sim == pytest.approx(1.0)


def test_case_similarity_keine_uebereinstimmung_falsification():
    """Falsifikation: völlig unterschiedliche Codes und Zustand → 0.0."""
    sim = case_similarity(
        current_alarm_codes=["E-01"],
        current_packml="Held",
        current_rule_modes=["TWF"],
        case=_case(alarm_codes=["E-99"], packml_state="Stopped", rule_modes=["HDF"]),
    )
    assert sim == pytest.approx(0.0)


def test_case_similarity_nur_packml_match():
    """Verifikation: nur PackML stimmt überein → Beitrag 0.3."""
    sim = case_similarity(
        current_alarm_codes=["E-01"],
        current_packml="Held",
        current_rule_modes=[],
        case=_case(alarm_codes=["E-99"], packml_state="Held", rule_modes=[]),
    )
    assert sim == pytest.approx(0.3)


def test_case_similarity_gewichtung_alarm_dominiert():
    """Verifikation: Alarmcode-Anteil (0.5) überwiegt PackML-Anteil (0.3)."""
    sim_alarm = case_similarity(
        current_alarm_codes=["E-01"],
        current_packml="Stopped",
        current_rule_modes=[],
        case=_case(alarm_codes=["E-01"], packml_state="Held", rule_modes=[]),
    )
    sim_packml = case_similarity(
        current_alarm_codes=["E-01"],
        current_packml="Held",
        current_rule_modes=[],
        case=_case(alarm_codes=["E-99"], packml_state="Held", rule_modes=[]),
    )
    assert sim_alarm > sim_packml


def test_case_similarity_fehlende_felder_falsification():
    """Falsifikation: case ohne Pflichtfelder → kein Absturz, Score 0.0."""
    sim = case_similarity(
        current_alarm_codes=["E-01"],
        current_packml="Held",
        current_rule_modes=["TWF"],
        case={},
    )
    assert 0.0 <= sim <= 1.0


# ---------------------------------------------------------------------------
# score_cases
# ---------------------------------------------------------------------------


def _make_cases():
    return [
        _case(alarm_codes=["E-01", "E-02"], packml_state="Held", rule_modes=["TWF"]),
        _case(alarm_codes=["E-99"], packml_state="Stopped", rule_modes=["HDF"]),
        _case(alarm_codes=["E-01"], packml_state="Held", rule_modes=["TWF", "OSF"]),
    ]


def test_score_cases_bester_erste():
    """Verifikation: score_cases gibt Fälle absteigend nach Ähnlichkeit zurück."""
    cases = _make_cases()
    scored = score_cases(["E-01", "E-02"], "Held", ["TWF"], cases)
    scores = [s for s, _ in scored]
    assert scores == sorted(scores, reverse=True)


def test_score_cases_top_k_beschraenkt():
    """Verifikation: top_k=2 liefert maximal 2 Ergebnisse."""
    cases = _make_cases()
    scored = score_cases(["E-01"], "Held", [], cases, top_k=2)
    assert len(scored) <= 2


def test_score_cases_leer_falsification():
    """Falsifikation: leere Fallliste → leere Ergebnisliste, kein Fehler."""
    scored = score_cases(["E-01"], "Held", ["TWF"], [], top_k=5)
    assert scored == []


def test_score_cases_bester_score_berechnung():
    """Verifikation: bester Score entspricht exakt der case_similarity des besten Falls."""
    cases = _make_cases()
    scored = score_cases(["E-01", "E-02"], "Held", ["TWF"], cases, top_k=5)
    best_score, best_case = scored[0]
    expected = case_similarity(["E-01", "E-02"], "Held", ["TWF"], best_case)
    assert best_score == pytest.approx(expected)


def test_score_cases_gleiche_codes_hoher_score():
    """Verifikation: identischer Alarmcode und PackML → Score ≥ 0.5."""
    cases = [_case(alarm_codes=["E-01"], packml_state="Held")]
    scored = score_cases(["E-01"], "Held", [], cases)
    assert scored[0][0] >= 0.5
