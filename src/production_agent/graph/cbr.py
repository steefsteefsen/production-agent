"""Case-Based Reasoning: Jaccard-Ähnlichkeit über Alarmcodes, PackML-Zustand und Regelmodus.

Rein funktional – keine DB-Zugriffe. Gewichtung aus decisions.yaml:
  0.5 × Jaccard(Alarmcodes)  +  0.3 × PackML-Übereinstimmung  +  0.2 × Jaccard(Regelmodi)
"""

from __future__ import annotations

from typing import Any


def jaccard(a: set, b: set) -> float:
    """Jaccard-Koeffizient; 0.0 wenn beide Mengen leer."""
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def case_similarity(
    current_alarm_codes: list[str],
    current_packml: str,
    current_rule_modes: list[str],
    case: dict[str, Any],
) -> float:
    """Ähnlichkeit zwischen aktuellem Zustand und einem Gold-Fall.

    Erwartet im case-Dict (alle optional):
      alarm_codes: list[str]  – Alarmcodes des historischen Falls
      packml_state: str        – PackML-Zustand des historischen Falls
      rule_modes: list[str]    – ausgelöste AI4I-Regelmodi des historischen Falls
    """
    alarm_sim = jaccard(set(current_alarm_codes), set(case.get("alarm_codes", [])))
    packml_match = 1.0 if case.get("packml_state", "") == current_packml else 0.0
    rule_sim = jaccard(set(current_rule_modes), set(case.get("rule_modes", [])))
    return 0.5 * alarm_sim + 0.3 * packml_match + 0.2 * rule_sim


def score_cases(
    current_alarm_codes: list[str],
    current_packml: str,
    current_rule_modes: list[str],
    cases: list[dict[str, Any]],
    top_k: int = 5,
) -> list[tuple[float, dict[str, Any]]]:
    """Ähnlichste Gold-Fälle berechnen; absteigende Liste, auf top_k beschränkt."""
    scored = [
        (case_similarity(current_alarm_codes, current_packml, current_rule_modes, c), c)
        for c in cases
    ]
    scored.sort(key=lambda x: -x[0])
    return scored[:top_k]
