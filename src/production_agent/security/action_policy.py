"""Sicherheitslogik für Handlungsempfehlungen.

„recommend safe actions" heißt: Der Agent empfiehlt, der Mensch entscheidet.
Jede Maßnahme wird klassifiziert. Nur Stufe INFORM darf ohne Freigabe angezeigt werden;
alles andere läuft über den Freigabeknoten (LangGraph interrupt). FORBIDDEN wird nie
vorgeschlagen – der Agent ist bewusst kein Teil des sicherheitsgerichteten Steuerungsteils
(ISO 13849 / IEC 61508 bleiben außen vor).
"""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, Field


class ActionLevel(StrEnum):
    INFORM = "inform"  # Information/Diagnose, kein Eingriff
    APPROVAL_REQUIRED = "approval_required"  # Eingriff nur nach menschlicher Freigabe
    FORBIDDEN = "forbidden"  # Nie empfehlen


class RecommendedAction(BaseModel):
    title: str
    description: str
    level: ActionLevel = ActionLevel.APPROVAL_REQUIRED
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = ""
    expected_effect_minutes: float | None = None
    policy_notes: list[str] = Field(default_factory=list)


_FORBIDDEN = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"schutz(einrichtung|tür|zaun|kreis)\w*\s+(überbrück|umgeh|deaktiv|abschalt)",
        r"not-?aus\w*\s+(überbrück|umgeh|deaktiv|quittier)",
        r"lichtschranke\w*\s+(überbrück|umgeh|deaktiv)",
        r"sicherheits\w*\s+(überbrück|umgeh|deaktiv|abschalt)",
        r"(bypass|override|disable)\s+(safety|e-?stop|guard|interlock)",
    )
]
_INFORM_ONLY = re.compile(
    r"^(prüfe|prüfen|kontrolliere|sichtprüfung|informiere|dokumentiere|melde|überwache)\b",
    re.IGNORECASE,
)


def classify(action_text: str) -> ActionLevel:
    if any(p.search(action_text) for p in _FORBIDDEN):
        return ActionLevel.FORBIDDEN
    if _INFORM_ONLY.match(action_text.strip()):
        return ActionLevel.INFORM
    return ActionLevel.APPROVAL_REQUIRED


def apply_policy(
    actions: list[RecommendedAction], confidence_threshold: float
) -> list[RecommendedAction]:
    """Filtert verbotene Maßnahmen, stuft ein und wendet die Konfidenzschwelle an.

    Die Schwelle ist eine wirtschaftliche Entscheidung (Falsch-Positiv = unnötiger Eingriff,
    Falsch-Negativ = längerer Stillstand) und wird bewusst konfigurierbar gehalten.
    """
    kept: list[RecommendedAction] = []
    for a in actions:
        level = classify(f"{a.title} {a.description}")
        if level == ActionLevel.FORBIDDEN:
            continue
        a.level = level
        if a.confidence < confidence_threshold and level != ActionLevel.INFORM:
            a.policy_notes.append(
                f"Konfidenz {a.confidence:.2f} unter Schwelle {confidence_threshold:.2f} – "
                "nur als Hypothese anzeigen, nicht als Empfehlung."
            )
        kept.append(a)
    return kept
