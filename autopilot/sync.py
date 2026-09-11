"""Sync-Paket für den Chat: eine Datei je Arbeitspaket, die Claude (im Projekt) alles gibt, was er braucht.

python autopilot/sync.py WP3          → autopilot/sync/WP3.md   (hochladen oder einfügen)
python autopilot/sync.py --status     → STATUS.md aktualisieren (Projektwissen im Chat)
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "autopilot" / "sync"


def _git(*a: str) -> str:
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout


def packet(wp_id: str) -> Path:
    tasks = {
        t["id"]: t
        for t in yaml.safe_load((ROOT / "autopilot/tasks.yaml").read_text(encoding="utf-8"))
    }
    t = tasks[wp_id]
    journal = (
        json.loads((ROOT / "autopilot/journal.json").read_text())
        if (ROOT / "autopilot/journal.json").exists()
        else []
    )
    entries = [e for e in journal if e["wp"] == wp_id]
    reviews = [e.get("review") for e in entries if e.get("review")]
    parts = [
        f"# Sync {wp_id} · {time.strftime('%Y-%m-%d %H:%M')}\n",
        f"## Ziel\n{t['prompt'][:600]}…\n",
        "## Gate\n`" + t["gate"] + "`\n",
        "## Review-Checkliste\n" + "\n".join(f"- {c}" for c in t["review_gate"]) + "\n",
    ]
    if entries:
        e = entries[-1]
        parts.append(
            f"## Journal (letzter Lauf)\nok={e['ok']} · Versuche {e['attempts']} · {e['minutes']} min · {e['turns']} Turns · {e['cost_usd']} USD\n\n{e['agent_summary']}\n\nDateien: {', '.join(e['files'])}\n\nGate-Ausgabe:\n```\n{e['gate_tail']}\n```\n"
        )
    if reviews:
        parts.append(
            "## Reviewer-Urteil\n```json\n"
            + json.dumps(reviews[-1], ensure_ascii=False, indent=1)[:4000]
            + "\n```\n"
        )
    parts.append("## Diff --stat\n```\n" + _git("diff", "--stat", "HEAD~1") + "\n```\n")
    for f in t.get("review_files", []):
        p = ROOT / f
        if p.exists():
            parts.append(f"## {f}\n```\n{p.read_text(encoding='utf-8')[:6000]}\n```\n")
    parts.append("## Offene Frage an Claude im Chat\n_(hier eintragen)_\n")
    OUT.mkdir(exist_ok=True)
    out = OUT / f"{wp_id}.md"
    out.write_text("\n".join(parts), encoding="utf-8")
    return out


def status() -> Path:
    st = (
        json.loads((ROOT / "autopilot/status.json").read_text())
        if (ROOT / "autopilot/status.json").exists()
        else {"wp": {}, "hours": 0}
    )
    tasks = yaml.safe_load((ROOT / "autopilot/tasks.yaml").read_text(encoding="utf-8"))
    rows = "\n".join(
        f"| {t['id']} | {t['agent']} | {'✅' if st['wp'].get(t['id']) else '⬜'} |" for t in tasks
    )
    md = (
        f"# STATUS – Production Agent PoC\nStand: {time.strftime('%Y-%m-%d %H:%M')} · Agentenzeit bisher {st.get('hours', 0)} h\n\n"
        "## Arbeitspakete\n| WP | Agent | Status |\n|---|---|---|\n" + rows + "\n\n"
        "## Letzte Journal-Einträge\n"
        + (
            (ROOT / "autopilot/journal.md").read_text(encoding="utf-8")[-3000:]
            if (ROOT / "autopilot/journal.md").exists()
            else "_noch keine_"
        )
        + "\n\n## Offene Entscheidungen\n- \n\n## Nächste Schritte\n- \n"
    )
    p = ROOT / "STATUS.md"
    p.write_text(md, encoding="utf-8")
    return p


if __name__ == "__main__":
    if "--status" in sys.argv:
        print(status())
    else:
        print(packet(sys.argv[1]))
