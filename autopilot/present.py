#!/usr/bin/env python3
"""Interaktive Präsentation des Projektablaufs: docs/presentation/index.html aus Fakten.

Quellen: git log (Commits), autopilot/journal/*.json (Läufe/Kosten/Reviews), autopilot/state/
orchestrator.json (Lanes/Merges), docs/sessions/*.md, docs/AENDERUNGEN.md, docs/adr/*.md,
coverage.json. Statische Seite, Daten inline als JSON (file:// lauffähig), sechs Tabs. Kein LLM.

  python autopilot/present.py            erzeugen, Pfad ausgeben
  python autopilot/present.py --stage    erzeugen und git add (für den Hook)
  python autopilot/present.py --check     erzeugen und Parsebarkeit prüfen; Exit 0/1
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "presentation" / "index.html"
sys.path.insert(0, str(Path(__file__).resolve().parent))

SCOPE_RE = re.compile(r"^(feat|fix|test|docs|adr|sec|chore)\(([^)]+)\):\s*(.*)$")
TABS = [
    ("ablauf", "Ablauf"),
    ("lanes", "Lanes"),
    ("entscheidungen", "Entscheidungen"),
    ("qualitaet", "Qualität"),
    ("kosten", "Kosten"),
    ("sitzungen", "Sitzungen"),
]


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True).stdout.decode(
        "utf-8", errors="replace"
    )


def classify(title: str) -> tuple[str, str]:
    """Typ und Scope aus dem Commit-Titel; ohne Konvention → ('sonstige', '')."""
    m = SCOPE_RE.match(title)
    return (m.group(1), m.group(2)) if m else ("sonstige", "")


def gather_commits() -> list[dict]:
    out = _git("log", "--reverse", "--pretty=format:%H%x1f%cI%x1f%s%x1f%b%x1e")
    commits = []
    for rec in out.split("\x1e"):
        rec = rec.strip("\n")
        if not rec or "\x1f" not in rec:
            continue
        sha, at, title, body = (rec.split("\x1f", 3) + ["", "", "", ""])[:4]
        typ, scope = classify(title)
        commits.append(
            {"sha": sha[:7], "at": at, "title": title, "type": typ, "scope": scope, "body": body}
        )
    return commits


def _read(path: Path, limit: int = 4000) -> str:
    return path.read_text(encoding="utf-8")[:limit] if path.exists() else ""


def gather_adrs() -> list[dict]:
    adrs = []
    for p in sorted((ROOT / "docs" / "adr").glob("*.md")):
        if p.name.startswith("0000"):
            continue
        t = p.read_text(encoding="utf-8")
        title = t.splitlines()[0].lstrip("# ").strip() if t else p.stem
        dec = ""
        m = re.search(r"## Entscheidung\s*\n(.+?)(?:\n##|\Z)", t, re.S)
        if m:
            dec = m.group(1).strip()[:400]
        adrs.append({"file": p.name, "title": title, "decision": dec})
    return adrs


def gather_sessions() -> list[dict]:
    return [
        {"file": p.name, "text": _read(p, 2000)}
        for p in sorted((ROOT / "docs" / "sessions").glob("*.md"))
    ]


def build_presentation(
    commits: list[dict],
    journal: list[dict],
    orch: dict | None,
    coverage: dict | None,
    adrs: list[dict],
    sessions: list[dict],
    generated_at: str | None = None,
) -> dict:
    runs = [
        {
            "wp": e.get("wp"),
            "at": e.get("at"),
            "ok": e.get("ok"),
            "attempts": e.get("attempts"),
            "minutes": e.get("minutes"),
            "cost_usd": e.get("cost_usd"),
            "turns": e.get("turns"),
            "review": (e.get("review") or {}).get("verdict"),
        }
        for e in journal
    ]
    costs: dict[str, float] = {}
    loops: dict[str, int] = {}
    for e in journal:
        costs[e.get("wp", "?")] = round(
            costs.get(e.get("wp", "?"), 0) + (e.get("cost_usd") or 0), 2
        )
        loops[e.get("wp", "?")] = loops.get(e.get("wp", "?"), 0) + 1
    lanes: dict[str, list[dict]] = {}
    if orch:
        for wp, w in orch.get("wp", {}).items():
            lanes.setdefault(w.get("lane", "?"), []).append(
                {
                    "wp": wp,
                    "status": w.get("status"),
                    "started_at": w.get("started_at"),
                    "finished_at": w.get("finished_at"),
                    "merge_sha": w.get("merge_sha"),
                }
            )
    return {
        "generated_at": generated_at or datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "commits": commits,
        "runs": runs,
        "lanes": lanes,
        "decisions": adrs,
        "quality": {
            "coverage_total": (coverage or {}).get("total"),
            "coverage_security": (coverage or {}).get("security"),
        },
        "costs": {"per_wp": costs, "loops": loops, "total": round(sum(costs.values()), 2)},
        "sessions": sessions,
    }


def render_html(data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    tabbar = "".join(
        f'<button class="tab{" active" if i == 0 else ""}" data-tab="{key}">{label}</button>'
        for i, (key, label) in enumerate(TABS)
    )
    panels = "".join(
        f'<section class="panel{" active" if i == 0 else ""}" id="panel-{key}">'
        f'<h2>{label}</h2><div class="body"></div></section>'
        for i, (key, label) in enumerate(TABS)
    )
    return f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8"><title>Production Agent – Ablauf</title>
<style>
:root{{--teal:#0b4f6c;--teal2:#005a64;--teal3:#006252;--wine:#5d0a1f;--sage:#679881}}
body{{font-family:system-ui,sans-serif;margin:0;background:#f4f7f8;color:#12313c}}
header{{background:var(--teal);color:#fff;padding:16px 24px}} header h1{{margin:0;font-size:19px}}
.tabs{{display:flex;gap:4px;background:var(--teal2);padding:0 16px}}
.tab{{background:none;border:0;color:#cfe0e4;padding:10px 14px;cursor:pointer;font-size:14px}}
.tab.active{{background:#f4f7f8;color:var(--teal);font-weight:600;border-radius:6px 6px 0 0}}
main{{padding:18px 24px;max-width:1100px;margin:0 auto}}
.panel{{display:none}} .panel.active{{display:block}}
.dot{{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px}}
.row{{background:#fff;border:1px solid #dde5e8;border-radius:6px;padding:8px 10px;margin-bottom:6px;font-size:13px}}
.bar{{height:14px;border-radius:3px;background:var(--teal3)}}
.card{{background:#fff;border:1px solid #dde5e8;border-radius:8px;padding:12px;margin-bottom:8px}}
h2{{font-size:16px;color:var(--teal)}}
</style></head>
<body>
<script id="data" type="application/json">{payload}</script>
<header><h1>Production Agent – Ablauf aus Fakten · Stand {data["generated_at"]}</h1></header>
<div class="tabs">{tabbar}</div>
<main>{panels}</main>
<script>
const D=JSON.parse(document.getElementById('data').textContent);
const C={{feat:'#005a64',fix:'#5d0a1f',test:'#679881',docs:'#0b4f6c',adr:'#006252',sec:'#5d0a1f',chore:'#9aa5ab',sonstige:'#9aa5ab'}};
function esc(s){{return (s||'').replace(/[&<>]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;'}}[c]));}}
function render(){{
 const b=k=>document.querySelector('#panel-'+k+' .body');
 b('ablauf').innerHTML=D.commits.map(c=>`<div class="row"><span class="dot" style="background:${{C[c.type]||'#9aa5ab'}}"></span><b>${{esc(c.type)}}${{c.scope?'('+esc(c.scope)+')':''}}</b> ${{esc(c.title)}} <small>${{esc(c.at)}} · ${{c.sha}}</small></div>`).join('')||'<p>keine Commits</p>';
 b('lanes').innerHTML=Object.keys(D.lanes).length?Object.entries(D.lanes).map(([l,ws])=>`<div class="row"><b>${{esc(l)}}</b>: ${{ws.map(w=>esc(w.wp)+' ['+esc(w.status)+']').join(', ')}}</div>`).join(''):'<p>orchestrator.json noch nicht vorhanden – Lanes erscheinen nach dem ersten Lauf.</p>';
 b('entscheidungen').innerHTML=D.decisions.map(a=>`<div class="card"><b>${{esc(a.title)}}</b><br><small>${{esc(a.file)}}</small><p>${{esc(a.decision)}}</p></div>`).join('')||'<p>keine ADRs</p>';
 b('qualitaet').innerHTML=`<div class="card">Coverage gesamt: <b>${{D.quality.coverage_total??'—'}} %</b> · security <b>${{D.quality.coverage_security??'—'}} %</b></div><div class="card">Läufe mit Review: ${{D.runs.filter(r=>r.review).map(r=>esc(r.wp)+':'+esc(r.review)).join(', ')||'—'}}</div>`;
 b('kosten').innerHTML=`<div class="card">Gesamt: <b>${{D.costs.total}} USD</b></div>`+Object.entries(D.costs.per_wp).map(([w,c])=>`<div class="row">${{esc(w)}}: ${{c}} USD · ${{D.costs.loops[w]||0}} Loops</div>`).join('')||'<p>keine Kosten</p>';
 b('sitzungen').innerHTML=D.sessions.map(s=>`<div class="card"><b>${{esc(s.file)}}</b><pre style="white-space:pre-wrap">${{esc(s.text)}}</pre></div>`).join('')||'<p>keine Sitzungsdateien</p>';
}}
document.querySelectorAll('.tab').forEach(t=>t.onclick=()=>{{
 document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));
 document.querySelectorAll('.panel').forEach(x=>x.classList.remove('active'));
 t.classList.add('active');document.getElementById('panel-'+t.dataset.tab).classList.add('active');
}});
document.onkeydown=e=>{{const t=[...document.querySelectorAll('.tab')];const i=t.findIndex(x=>x.classList.contains('active'));
 if(e.key==='ArrowRight'&&i<t.length-1)t[i+1].click();if(e.key==='ArrowLeft'&&i>0)t[i-1].click();}};
render();
</script>
</body></html>
"""


def _coverage() -> dict | None:
    cov = ROOT / ".guardian" / "coverage.json"
    if not cov.exists():
        return None
    data = json.loads(cov.read_text(encoding="utf-8"))
    files = {k.replace("\\", "/"): v for k, v in data.get("files", {}).items()}
    sec = [v["summary"]["percent_covered"] for k, v in files.items() if "/security/" in k]
    return {
        "total": round(data.get("totals", {}).get("percent_covered", 0)),
        "security": round(min(sec)) if sec else None,
    }


def generate(stage: bool = False) -> Path:
    import journal as journal_mod  # noqa: PLC0415

    orch_path = ROOT / "autopilot" / "state" / "orchestrator.json"
    orch = json.loads(orch_path.read_text(encoding="utf-8")) if orch_path.exists() else None
    data = build_presentation(
        commits=gather_commits(),
        journal=journal_mod.load_all(),
        orch=orch,
        coverage=_coverage(),
        adrs=gather_adrs(),
        sessions=gather_sessions(),
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render_html(data), encoding="utf-8")
    if stage:
        subprocess.run(["git", "add", str(OUT.relative_to(ROOT))], cwd=ROOT)
    return OUT


def check() -> int:
    generate(stage=True)
    html = OUT.read_text(encoding="utf-8")
    m = re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S)
    if not m:
        print("presentation: kein Daten-Block")
        return 1
    data = json.loads(m.group(1))
    print(f"presentation aktuell: {len(data['commits'])} Commits, {len(TABS)} Tabs")
    return 0


if __name__ == "__main__":
    if "--check" in sys.argv:
        sys.exit(check())
    p = generate(stage="--stage" in sys.argv)
    print(p)
