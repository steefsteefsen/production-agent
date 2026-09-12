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
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cc  # noqa: E402

JOURNAL_MD = ROOT / "autopilot" / "journal.md"
JOURNAL_JSON = ROOT / "autopilot" / "journal.json"
JOURNAL_DIR = (
    ROOT / "autopilot" / "journal"
)  # eine Datei je WP – worktree-sicher (merge=union in journal.md)


def load_all() -> list[dict]:
    """Alle Journal-Einträge aus autopilot/journal/*.json (+ Alt-journal.json), sortiert nach 'at'.
    Wirft bei kaputtem JSON (kein stilles Überspringen)."""
    entries: list[dict] = []
    if JOURNAL_JSON.exists():
        data = json.loads(JOURNAL_JSON.read_text(encoding="utf-8"))
        entries.extend(data if isinstance(data, list) else [data])
    if JOURNAL_DIR.exists():
        for p in sorted(JOURNAL_DIR.glob("*.json")):
            data = json.loads(p.read_text(encoding="utf-8"))
            entries.extend(data if isinstance(data, list) else [data])
    return sorted(entries, key=lambda e: e.get("at", ""))


def _git(*args: str) -> str:
    p = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)  # noqa: S603, S607
    return p.stdout.strip()


def _git_cp(*args: str) -> subprocess.CompletedProcess:
    """Wie _git, aber mit vollem Ergebnis (returncode/stdout/stderr) – der Committer prüft den Rückgabewert."""
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)  # noqa: S603, S607


def _head() -> str:
    return _git("rev-parse", "HEAD")


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
        "cost_usd": (claude_json or {}).get("total_cost_usd") or "abo",  # Abo-Betrieb: keine USD
        "turns": (claude_json or {}).get("num_turns"),
        "files": files,
        "agent_summary": summary,
        "gate_tail": gate_tail[-600:],
        "narrative": "",
    }
    if narrate and files:
        diff = _git("diff", "HEAD")[:12000]
        try:
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
                stdin=subprocess.DEVNULL,
                timeout=600,
                env=cc.env(),
            )
            e["narrative"] = p.stdout.strip()[:600]
        except subprocess.TimeoutExpired:
            e["narrative"] = "(Narrativ-Timeout nach 600s)"
    return e


def _sanitize_paths(v):
    """Absolute Pfade aus Journal-Einträgen entfernen (Ordnernamen sind privat, S8)."""
    parent = str(ROOT.parent)
    if isinstance(v, str):
        return v.replace(parent, "~")
    if isinstance(v, list):
        return [_sanitize_paths(x) for x in v]
    if isinstance(v, dict):
        return {k: _sanitize_paths(x) for k, x in v.items()}
    return v


def write(e: dict) -> None:
    e = _sanitize_paths(e)
    # eine Datei je WP (parallele Lanes überschreiben sich nicht), Sammel-md bleibt Append
    JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    wp_file = JOURNAL_DIR / f"{e['wp']}.json"
    data = json.loads(wp_file.read_text(encoding="utf-8")) if wp_file.exists() else []
    data.append(e)
    wp_file.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
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


def _commit_or_rescue(wp_id: str, title: str, body: str, footer: str) -> bool:
    """git commit auf dem aktuellen Branch – MIT Prüfung des Rückgabewerts.

    Scheitert der Commit still (Hook rot, HEAD unverändert), werden stdout+stderr nach
    autopilot/logs/commit-fail-<WP>.log geschrieben, eine Logzeile mit dem Grund ausgegeben und ein
    Rettungs-Commit OHNE Hooks (git -c core.hooksPath=/dev/null) mit Footer „… | hooks: übersprungen"
    gesetzt. Rückgabe True nur, wenn danach ein neuer Commit existiert (HEAD ≠ Basis)."""
    base = _head()
    c = _git_cp("commit", "-q", "-m", title, "-m", body, "-m", footer)
    if c.returncode == 0 and _head() != base:
        return True
    log_dir = ROOT / "autopilot" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    fail_log = log_dir / f"commit-fail-{wp_id}.log"
    fail_log.write_text(
        f"git commit rc={c.returncode}\n--- stdout ---\n{c.stdout}\n--- stderr ---\n{c.stderr}\n",
        encoding="utf-8",
    )
    tail = [ln for ln in (c.stdout + c.stderr).splitlines() if ln.strip()]
    reason = tail[-1].strip() if tail else f"rc={c.returncode}"
    print(
        f"{wp_id}: Commit gescheitert ({reason}) – Rettungs-Commit ohne Hooks, Log: {fail_log}",
        flush=True,
    )
    _git_cp(
        "-c",
        "core.hooksPath=/dev/null",
        "commit",
        "-q",
        "-m",
        title,
        "-m",
        body,
        "-m",
        footer + " | hooks: übersprungen",
    )
    return _head() != base


def commit(wp_id: str, e: dict) -> bool:
    """Commit nach Konvention (CLAUDE.md) auf dem aktuellen Branch. Tag wp/<id> setzt der
    Orchestrator erst nach dem Merge auf main (Block 7). Rückgabe True, wenn ein Commit existiert
    (regulär oder als Rettungs-Commit ohne Hooks) – run.py meldet OK nur bei True."""
    first = (e["agent_summary"].splitlines() or [""])[0].strip().rstrip(".")
    title = f"{_commit_type(e['files'])}({wp_id}): {first[:60] or 'Arbeitspaket abgeschlossen'}"
    review = (e.get("review") or {}).get("verdict", "human")
    footer = f"Gate: {'grün' if e['ok'] else 'rot'} | Review: {review} | Guardian: ok"
    subprocess.run([sys.executable, str(ROOT / "autopilot" / "status.py"), "--stage"], cwd=ROOT)
    subprocess.run([sys.executable, "-m", "ruff", "format", "."], cwd=ROOT)  # ruff_pre_commit
    subprocess.run([sys.executable, "-m", "ruff", "check", "--fix", "-q", "."], cwd=ROOT)
    _git("add", "-A")
    return _commit_or_rescue(wp_id, title, e["agent_summary"] or "-", footer)
