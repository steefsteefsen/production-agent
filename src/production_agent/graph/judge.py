"""LLM-as-Judge: unabhängige Beleg-Prüfung der Maßnahmen aus Knoten 6 (ADR-0011).

Bewusst getrennter Kontext: der Judge sieht je Maßnahme NUR den Maßnahmentext (Titel,
Beschreibung) und den zitierten Beleg im Original – nicht die Hypothese aus Knoten 4 und nicht die
Begründung (rationale) bzw. Konversation aus Knoten 6. So kann er die Begründung des vorschlagenden
Modells nicht einfach übernehmen, sondern prüft unabhängig. Kein Auto-Verwerfen: das Ergebnis
(verified + judge_note) wird nur durchgereicht und am Freigabeknoten angezeigt.
"""

from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from production_agent.graph.prompts import SYSTEM_JUDGE
from production_agent.graph.structured import invoke_structured


class JudgeVerdict(BaseModel):
    """Strukturierte Judge-Ausgabe je Maßnahme."""

    verified: bool
    judge_note: str = ""


def cited_evidence(action: dict, knowledge: list[dict]) -> list[dict]:
    """Original-Belege, die die Maßnahme in ihrer rationale zitiert (Vorfall-IDs aus knowledge).

    Nur ähnliche Vorfälle mit event_id gelten als zitierbarer Beleg (Nachbedingung Knoten 6). Gibt
    die Belege im Original zurück – die rationale selbst bleibt dem Judge bewusst verborgen.
    """
    rationale = str(action.get("rationale", "") or "")
    incidents = [
        k for k in (knowledge or []) if isinstance(k, dict) and k.get("event_id") not in (None, "")
    ]
    return [k for k in incidents if str(k["event_id"]) in rationale]


def _judge_input(action: dict, evidence: list[dict]) -> str:
    """Nur Maßnahmentext + Beleg im Original – kein Leck von Hypothese oder rationale."""
    return json.dumps(
        {
            "massnahme": {
                "title": action.get("title", ""),
                "description": action.get("description", ""),
            },
            "zitierter_beleg": evidence,
        },
        ensure_ascii=False,
        default=str,
    )


def judge_action(chain, action: dict, evidence: list[dict]) -> dict:
    """Eine Maßnahme unabhängig gegen ihren Beleg prüfen. Gibt {title, verified, judge_note}."""
    messages = [
        SystemMessage(content=SYSTEM_JUDGE),
        HumanMessage(content=f"Prüfauftrag:\n{_judge_input(action, evidence)}"),
    ]
    verdict: JudgeVerdict = invoke_structured(chain, messages, JudgeVerdict)
    return {
        "title": action.get("title", ""),
        "verified": bool(verdict.verified),
        "judge_note": verdict.judge_note,
    }
