"""Deterministisches Mock-LLM für Knoten 4 und 6 (LLM_MODE=mock).

Kein API-Schlüssel: die beiden LLM-Knoten erhalten ihren Kontext als JSON in einer HumanMessage.
Das Mock liest diesen Kontext (echte Werkzeugdaten) und leitet Hypothese und Maßnahmen regelbasiert
ab – die Ursache aus den ähnlichen Vorfällen, jede Maßnahme mit einer belegenden Vorfall-ID
(event_id) aus downtime_events_gold (Nachbedingung Knoten 6). Für E2E-Replay und CI, nicht für die
Produktion (dort ChatAnthropic über LLM_MODE=live).
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from langchain_core.runnables import RunnableLambda

from production_agent.graph.judge import JudgeVerdict
from production_agent.graph.state import Hypothesis
from production_agent.graph.workflow import (
    _ActionsOutput,
    _first_alarm_code,
    _HypothesesOutput,
)
from production_agent.security.action_policy import ActionLevel, RecommendedAction


def _context(messages) -> dict:
    """Den JSON-Kontext aus der HumanMessage (f"Kontext:\\n{json}") herauslösen."""
    for m in reversed(messages):
        content = getattr(m, "content", "") or ""
        idx = content.find("{")
        if idx >= 0:
            try:
                return json.loads(content[idx:])
            except ValueError:
                continue
    return {}


def _incidents(knowledge: list) -> list[dict]:
    return [k for k in knowledge if isinstance(k, dict) and k.get("event_id") not in (None, "")]


def _mock_narrow_cause(messages) -> _HypothesesOutput:
    """Mehrere Ursachenkandidaten (nicht nur die beste), deterministisch aus den Vorfällen:
    die häufigste reason_code ist die beste (Konfidenz 0.80, über Default-Schwelle 0.60), weitere
    reason_codes bzw. plausible Standardcodes werden als Alternativen mit fallender Konfidenz
    (unter Schwelle) ergänzt – so zeigt der Bediener-Tab das Balkendiagramm realistisch."""
    ctx = _context(messages)
    alarms = ctx.get("alarms", [])
    incidents = _incidents(ctx.get("knowledge", []))
    reason_codes = [str(i.get("reason_code")) for i in incidents if i.get("reason_code")]
    ranking = [c for c, _ in Counter(reason_codes).most_common()]
    best_code = ranking[0] if ranking else "STO-UNBEKANNT"
    first_code = _first_alarm_code(alarms)
    event_ids = [str(i["event_id"]) for i in incidents[:2]]
    evidence = [e for e in ([first_code] + event_ids) if e] or ["(keine Evidenz)"]
    durations = [float(i.get("duration_min", 0) or 0) for i in incidents if i.get("duration_min")]
    downtime = round(sum(durations) / len(durations), 1) if durations else 30.0

    candidates = [
        Hypothesis(
            cause=f"Störung {best_code}, abgeleitet aus {len(incidents)} ähnlichen Vorfällen",
            reason_code=best_code,
            confidence=0.80,
            evidence=evidence,
            expected_downtime_min=downtime,
        )
    ]
    # Alternativen: weitere reason_codes aus den Vorfällen, sonst plausible Standardcodes.
    fallback = ["STO-SENSOR", "QUAL-NIO", "STO-ELEK", "STO-ANTRIEB", "MAT-STAU"]
    seen = {best_code}
    alt_codes: list[str] = []
    for c in [*ranking[1:], *fallback]:
        if c not in seen:
            seen.add(c)
            alt_codes.append(c)
    for code, conf in zip(alt_codes[:3], (0.45, 0.34, 0.22), strict=False):
        candidates.append(
            Hypothesis(
                cause=f"Alternative Ursache {code} (nachrangig)",
                reason_code=code,
                confidence=conf,
                evidence=[first_code] if first_code else [],
                expected_downtime_min=round(downtime * 0.8, 1),
            )
        )
    return _HypothesesOutput(candidates=candidates)


def _mock_derive_actions(messages) -> _ActionsOutput:
    ctx = _context(messages)
    incidents = _incidents(ctx.get("knowledge", []))
    hypo: dict[str, Any] = ctx.get("hypothesis", {})
    reason_code = hypo.get("reason_code", "")
    conf = min(float(hypo.get("confidence", 0.8) or 0.8), 0.80)
    ids = [str(i["event_id"]) for i in incidents]
    templates = [
        (
            "Störung nach dokumentiertem Vorgehen beheben",
            "Bewährte Maßnahme aus ähnlichem Vorfall übernehmen.",
        ),
        (
            "Betroffene Station prüfen und wieder freigeben",
            "Sichtprüfung, Ursache beseitigen, kontrollierter Wiederanlauf.",
        ),
    ]
    actions: list[RecommendedAction] = []
    for k, (title, desc) in enumerate(templates):
        vid = ids[k % len(ids)] if ids else ""
        rationale = (
            f"Beleg: ähnlicher Vorfall {vid} ({reason_code})"
            if vid
            else "keine Vorfall-ID verfügbar"
        )
        actions.append(
            RecommendedAction(
                title=title,
                description=desc,
                level=ActionLevel.APPROVAL_REQUIRED,
                confidence=conf,
                rationale=rationale,
            )
        )
    return _ActionsOutput(actions=actions)


def _mock_judge(messages) -> JudgeVerdict:
    """Deterministischer Judge: bestätigt eine Maßnahme, wenn im zitierten Beleg-Kontext ein
    Vorfall (event_id) vorliegt; fehlt der Beleg (manipuliert/entfernt), wird sie NICHT bestätigt.
    Der Judge lässt sich bewusst nicht vom Maßnahmentext selbst überzeugen."""
    ctx = _context(messages)
    evidence = ctx.get("zitierter_beleg", []) or []
    incident = next(
        (e for e in evidence if isinstance(e, dict) and e.get("event_id") not in (None, "")),
        None,
    )
    if incident is not None:
        return JudgeVerdict(
            verified=True,
            judge_note=f"Beleg Vorfall {incident['event_id']} stützt die Maßnahme unabhängig.",
        )
    return JudgeVerdict(
        verified=False,
        judge_note="Kein belegender Vorfall im zitierten Kontext – nicht unabhängig gestützt.",
    )


def mock_judge_chain() -> RunnableLambda:
    """Einzelne Judge-Chain (für build_graph-Fallback, wenn ein llm-dict kein 'judge' liefert)."""
    return RunnableLambda(_mock_judge)


def mock_chains() -> dict:
    """Chains für build_graph(llm=...): narrow_cause, derive_actions und judge (Beleg-Prüfung)."""
    return {
        "narrow_cause": RunnableLambda(_mock_narrow_cause),
        "derive_actions": RunnableLambda(_mock_derive_actions),
        "judge": RunnableLambda(_mock_judge),
    }


# --- Rückkopplungs-Vervollständigung (LLM_MODE=mock, Ersatz für den echten Haiku-Aufruf) --------
# Beispiel-Rohtext je Ursachenklasse. Nur der Mock-Fallback, wenn der Bediener nichts Eigenes
# eingibt: vorher stand für ALLE Fälle der STO-FOLIE-Text ("Rolle neu eingespannt, nachjustiert"),
# sodass er fälschlich auch bei STO-ANTRIEB (Lagerdefekt) o. ä. erschien.
_FEEDBACK_BEISPIEL: dict[str, str] = {
    "STO-FOLIE": "Rolle neu eingespannt, Andruckrolle nachjustiert",
    "STO-ANTRIEB": "Antriebslager getauscht, Riemenspannung geprüft",
    "STO-SENSOR": "Sensor gereinigt und neu justiert",
    "QUAL-NIO": "Prüfparameter nachgeschärft, NIO-Charge aussortiert",
    "STO-ELEK": "elektrischen Anschluss geprüft, defekte Sicherung ersetzt",
    "MAT-STAU": "Materialstau an der Zuführung beseitigt",
}
# der generische Frontend-Default, der bisher für jeden Fall unverändert durchgereicht wurde
_FEEDBACK_DEFAULT_ROHTEXT = "rolle neu eingespannt, nachjustiert"


def mock_feedback_completion(raw: str, reason_code: str) -> str:
    """Deterministische Rückkopplungs-Vervollständigung ohne API (Tests/Demo), Ersatz für den
    echten Haiku-Aufruf im Mock-Modus.

    Der Beispiel-Rohtext wird aus dem tatsächlichen reason_code abgeleitet, wenn der Bediener nichts
    Eigenes eingegeben hat (oder nur den generischen UI-Default) – sonst erschiene der STO-FOLIE-
    Text auch bei anderen Ursachen. Echte Bedienereingaben werden unverändert übernommen.
    """
    text = (raw or "").strip()
    if not text or text.rstrip(" .").lower() == _FEEDBACK_DEFAULT_ROHTEXT:
        text = _FEEDBACK_BEISPIEL.get(reason_code, "Ursache vor Ort geprüft und behoben")
    rc = f" ({reason_code})" if reason_code else ""
    return (
        f"Ereignis{rc}: {text}. "
        "Ursache: vor Ort bestätigt. "
        "Maßnahme: nach dokumentiertem Vorgehen behoben, Station geprüft. "
        "Wiederanlauf: kontrolliert über Execute-Schritt, keine Auffälligkeiten."
    )
