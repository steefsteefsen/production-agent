"""Kontextfreier Review – eine frische Claude-Instanz beurteilt ein Arbeitspaket.

Trennung der Rollen: Der Builder (Subagent) kann den Reviewer nicht aufrufen – der Reviewer ist eine
Funktion von run.py, kein Werkzeug und kein MCP. Er sieht nur: Review-Checkliste, Diff, Tests, die in
tasks.yaml benannten Dokumente. Nicht: den Verlauf des Builders. Anderes Modell als der Builder
(Standard Opus prüft Sonnet), damit sich blinde Flecken nicht teilen. Ausgabe ist ein JSON-Urteil mit Schema.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cc  # noqa: E402

SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["pass", "fail", "escalate"]},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "check": {"type": "string"},
                    "result": {"type": "string", "enum": ["pass", "fail", "unclear"]},
                    "evidence": {"type": "string"},
                    "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                },
                "required": ["check", "result", "evidence", "severity"],
            },
        },
        "question_for_human": {"type": "string"},
        "summary": {"type": "string"},
    },
    "required": ["verdict", "items", "summary"],
}

SYSTEM = (
    "Du bist ein unabhängiger Prüfer für ein Arbeitspaket eines PoC (Production Agent, LangGraph + MCP). "
    "Du kennst den Bauverlauf nicht und sollst ihn nicht erraten. Prüfe ausschließlich die Checkliste gegen "
    "Diff, Tests und Dokumente. Jede Bewertung braucht einen konkreten Beleg (Dateiname, Zeile, Testname). "
    "Unbelegbares ist 'unclear'. Sicherheitsverstöße (freies SQL, ausführende Maßnahme ohne Freigabe, "
    "verbotene Maßnahme, Secrets, Leck der laufenden Störung in die Historie) sind immer severity high und "
    "führen zu 'fail'. 'escalate', wenn eine Entscheidung gebraucht wird, die nur der Auftraggeber treffen "
    "kann – stelle sie als eine Frage. Antworte nur im vorgegebenen JSON-Schema, auf Deutsch."
)


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout


def build_packet(wp_id: str, checklist: list[str], files: list[str], gate_tail: str) -> str:
    diff = _git("diff", "HEAD")[:40000]
    docs = []
    for f in files:
        p = ROOT / f
        if p.exists():
            docs.append(f'\n<file path="{f}">\n{p.read_text(encoding="utf-8")[:12000]}\n</file>')
    return (
        f"# Review {wp_id}\n\n## Checkliste\n"
        + "\n".join(f"- {c}" for c in checklist)
        + f"\n\n## Gate-Ausgabe\n{gate_tail}\n\n## Diff gegen HEAD\n```diff\n{diff}\n```\n\n## Dokumente\n"
        + "".join(docs)
    )


def review(
    wp_id: str, checklist: list[str], files: list[str], gate_tail: str, model: str | None = None
) -> dict:
    model = model or cc.model("reviewer")
    packet = build_packet(wp_id, checklist, files, gate_tail)
    cmd = [
        "claude",
        "-p",
        packet,
        "--model",
        model,
        "--append-system-prompt",
        SYSTEM,
        "--permission-mode",
        "dontAsk",
        "--allowedTools",
        "Read,Grep,Glob",  # lesen ja, ändern nie
        "--max-turns",
        "15",
        "--output-format",
        "json",
        "--json-schema",
        json.dumps(SCHEMA),
    ]
    try:
        p = subprocess.run(
            cmd,
            cwd=ROOT,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=600,
            env=cc.env(),
        )
    except subprocess.TimeoutExpired:
        return {
            "verdict": "escalate",
            "items": [],
            "summary": "Reviewer-Timeout nach 600s",
            "_cost_usd": None,
        }
    try:
        out = json.loads(p.stdout)
        verdict = out.get("structured_output") or json.loads(out.get("result", "{}"))
    except (json.JSONDecodeError, TypeError):
        verdict = {
            "verdict": "escalate",
            "items": [],
            "summary": f"Reviewer-Antwort nicht lesbar: {p.stdout[:300]}",
        }
    verdict["_cost_usd"] = (
        out.get("total_cost_usd")
        if isinstance(p.stdout, str) and p.stdout.startswith("{")
        else None
    )
    return verdict


def format_verdict(v: dict) -> str:
    lines = [f"Reviewer: {v.get('verdict', '?').upper()} – {v.get('summary', '')}"]
    for it in v.get("items", []):
        mark = {"pass": "✓", "fail": "✗", "unclear": "?"}.get(it["result"], "?")
        lines.append(f"  {mark} [{it['severity']}] {it['check']} — {it['evidence']}")
    if v.get("question_for_human"):
        lines.append(f"  Frage an dich: {v['question_for_human']}")
    return "\n".join(lines)
