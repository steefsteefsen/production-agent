"""Journal: nach jedem Arbeitspaket ein deterministischer Eintrag – ohne Subagent.

Quelle sind Fakten, die der Lauf ohnehin erzeugt: die Abschlussmeldung des Agents (drei Sätze: gebaut,
getestet, offen – so verlangt es jede .claude/agents/*.md), git diff --stat, Gate-Ergebnis, Kosten, Turns.
Optional (--narrate) fasst Haiku den Diff in drei Sätzen zusammen – Cent-Beträge, kein zweiter Agent.
Ausgabe: autopilot/journal.md (lesbar) und autopilot/journal.json (Import im Cockpit, Tab „Vorgehen").
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JOURNAL_MD = ROOT / "autopilot" / "journal.md"
JOURNAL_JSON = ROOT / "autopilot" / "journal.json"


def _git(*args: str) -> str:
    p = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)  # noqa: S603, S607
    return p.stdout.strip()


def entry(
    wp_id: str,
    agent: str,
    attempts: int,
    ok: bool,
    claude_json: dict | None,
    gate_tail: str,
    seconds: float,
    narrate: bool = False,
) -> dict:
    summary = (claude_json or {}).get("result", "").strip()[:1200]
    diff_stat = _git("diff", "--stat", "HEAD")
    files = [ln.split("|")[0].strip() for ln in diff_stat.splitlines() if "|" in ln]
    e = {
        "wp": wp_id,
        "agent": agent,
        "at": time.strftime("%Y-%m-%d %H:%M"),
        "ok": ok,
        "attempts": attempts,
        "minutes": round(seconds / 60, 1),
        "cost_usd": (claude_json or {}).get("total_cost_usd"),
        "turns": (claude_json or {}).get("num_turns"),
        "files": files,
        "agent_summary": summary,
        "gate_tail": gate_tail[-600:],
        "narrative": "",
    }
    if narrate and files:
        diff = _git("diff", "HEAD")[:12000]
        p = subprocess.run(  # noqa: S603, S607
            [
                "claude",
                "-p",
                f"Fasse diese Änderung in drei deutschen Sätzen für ein Projektjournal zusammen (was, warum, offen):\n{diff}",
                "--model",
                "haiku",
                "--max-turns",
                "1",
                "--output-format",
                "text",
                "--permission-mode",
                "dontAsk",
            ],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        e["narrative"] = p.stdout.strip()[:600]
    return e


def write(e: dict) -> None:
    data = json.loads(JOURNAL_JSON.read_text()) if JOURNAL_JSON.exists() else []
    data.append(e)
    JOURNAL_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    status = "✅" if e["ok"] else "❌"
    block = (
        f"\n## {e['at']} · {e['wp']} · {e['agent']} · {status} (Versuche {e['attempts']}, "
        f"{e['minutes']} min, {e['turns']} Turns, {e['cost_usd']} USD)\n"
        f"**Agent:** {e['agent_summary'] or '–'}\n\n"
        + (f"**Journal:** {e['narrative']}\n\n" if e["narrative"] else "")
        + f"**Dateien:** {', '.join(e['files']) or '–'}\n"
    )
    with JOURNAL_MD.open("a", encoding="utf-8") as fh:
        if fh.tell() == 0:
            fh.write("# Projektjournal – automatisch je Arbeitspaket\n")
        fh.write(block)


def _commit_type(files: list[str]) -> str:
    if files and all(f.startswith("docs/adr/") for f in files):
        return "adr"
    if files and all(f.startswith("docs/") or f == "README.md" for f in files):
        return "docs"
    if files and all(f.startswith("tests/") for f in files):
        return "test"
    if any("/security/" in f for f in files):
        return "sec"
    return "feat"


def commit(wp_id: str, e: dict) -> None:
    """Commit nach Konvention (CLAUDE.md): <typ>(<WP>): <Titel> · Body · Footer. Danach Tag wp/<id>."""
    first = (e["agent_summary"].splitlines() or [""])[0].strip().rstrip(".")
    title = f"{_commit_type(e['files'])}({wp_id}): {first[:60] or 'Arbeitspaket abgeschlossen'}"
    review = (e.get("review") or {}).get("verdict", "human")
    footer = f"Gate: {'grün' if e['ok'] else 'rot'} | Review: {review} | Guardian: ok"
    subprocess.run([sys.executable, str(ROOT / "autopilot" / "status.py"), "--stage"], cwd=ROOT)
    _git("add", "-A")
    _git("commit", "-q", "-m", title, "-m", e["agent_summary"] or "-", "-m", footer)
    _git("tag", "-f", f"wp/{wp_id}")
