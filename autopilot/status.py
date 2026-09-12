#!/usr/bin/env python3
"""Projektstatus deterministisch aus dem Repo erzeugen: docs/status/status.json + index.html.

Quellen: autopilot/tasks.yaml (Pakete), autopilot/journal.json (+ autopilot/journal/*.json),
git log/Tags, coverage.json (Coverage), Testfunktionszahl, Guardian. Kein LLM, keine externen
Abhängigkeiten. Fortschritt und Zeitstempel kommen so aus dem Repo, nicht aus manuellem Einfügen.

Aufrufe:
  python autopilot/status.py            erzeugen, schreiben, beide Pfade ausgeben
  python autopilot/status.py --stage    erzeugen, schreiben, git add (für Hooks/Journal)
  python autopilot/status.py --check     erzeugen, schreiben, staged; prüft frisch (<10 min); Exit 0/1
  python autopilot/status.py --json      status.json auf stdout
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
STATUS_DIR = ROOT / "docs" / "status"
STEP_NAMES = ["Gate grün", "Review", "Commit", "Tag", "Sync-Paket"]
SCOPE_RE = re.compile(r"^(?:feat|fix|test|docs|adr|sec|chore)\(([^)]+)\):")
DOC_SECTIONS = [
    ("Entscheidungen (ADRs)", lambda rel: rel.startswith("adr/")),
    (
        "Betrieb",
        lambda rel: (
            rel.startswith("betriebsanweisung/")
            or rel in ("guardian.md", "orchestrator.md", "chat_interface.md")
        ),
    ),
    ("Tests", lambda rel: rel in ("test_strategy.md", "test_cases.md")),
    ("Verlauf", lambda rel: rel.startswith("sessions/") or rel == "AENDERUNGEN.md"),
]


# --- Quellen -----------------------------------------------------------------------------


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout


def load_journal_file(path: str | Path) -> object:
    """Lädt eine Journal-Datei. Wirft bei kaputtem JSON (kein stilles 0 %)."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_journal() -> list[dict]:
    entries: list[dict] = []
    jf = ROOT / "autopilot" / "journal.json"
    if jf.exists():
        data = load_journal_file(jf)
        entries.extend(data if isinstance(data, list) else [data])
    jdir = ROOT / "autopilot" / "journal"
    if jdir.exists():
        for p in sorted(jdir.glob("*.json")):
            data = load_journal_file(p)
            entries.extend(data if isinstance(data, list) else [data])
    return entries


def gather_commits() -> list[dict]:
    out = _git("log", "--pretty=format:%H%x1f%s%x1f%cI")
    commits: list[dict] = []
    for line in out.splitlines():
        if "\x1f" not in line:
            continue
        sha, title, at = line.split("\x1f", 2)
        m = SCOPE_RE.match(title)
        commits.append({"sha": sha, "title": title, "at": at, "scope": m.group(1) if m else ""})
    return commits


def gather_tags() -> set[str]:
    return {
        t.split("/", 1)[1] for t in _git("tag", "-l", "wp/*").splitlines() if t.startswith("wp/")
    }


def head_sha() -> str:
    return (
        _git("rev-parse", "HEAD").strip() if _git("rev-parse", "--verify", "HEAD").strip() else ""
    )


def branch() -> str:
    return _git("rev-parse", "--abbrev-ref", "HEAD").strip() or "main"


def count_tests() -> int:
    n = 0
    tdir = ROOT / "tests"
    for p in tdir.rglob("test_*.py"):
        if "e2e" in p.parts:
            continue
        n += len(re.findall(r"^\s*def test_", p.read_text(encoding="utf-8"), re.M))
    return n


def pytest_count() -> int:
    """Echte Testanzahl (inkl. Parametrisierung) über pytest --collect-only; Fallback: Funktionszahl."""
    r = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-o",
            "addopts=",
            "-p",
            "no:warnings",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    m = re.search(r"(\d+) tests? collected", r.stdout)
    if m:
        return int(m.group(1))
    nodes = [ln for ln in r.stdout.splitlines() if "::" in ln]
    return len(nodes) or count_tests()


def read_coverage() -> dict | None:
    cov = ROOT / ".guardian" / "coverage.json"  # nur der volle Lauf schreibt hierhin
    if not cov.exists():
        return None
    data = json.loads(cov.read_text(encoding="utf-8"))
    files = {k.replace("\\", "/"): v for k, v in data.get("files", {}).items()}
    total = round(data.get("totals", {}).get("percent_covered", 0))
    sec = [v["summary"]["percent_covered"] for k, v in files.items() if "/security/" in k]
    return {"total": total, "security": round(min(sec)) if sec else None, "files": files}


def gather_structure(coverage: dict | None) -> list[dict]:
    base = ROOT / "src" / "production_agent"
    dirs: dict[str, list[str]] = {}
    for p in base.rglob("*.py"):
        if p.name == "__init__.py":
            continue
        rel = p.relative_to(ROOT).as_posix()
        d = p.parent.relative_to(base).as_posix()
        dirs.setdefault("(root)" if d == "." else d, []).append(rel)
    out: list[dict] = []
    for d in sorted(dirs):
        files = dirs[d]
        pct: int | None = None
        if coverage:
            cf = [coverage["files"][f] for f in files if f in coverage["files"]]
            stmts = sum(c["summary"]["num_statements"] for c in cf)
            covd = sum(c["summary"]["covered_lines"] for c in cf)
            pct = round(covd / stmts * 100) if stmts else 100
        tcount = 0
        needle = "production_agent" if d == "(root)" else f"production_agent.{d.replace('/', '.')}"
        for tp in (ROOT / "tests").rglob("test_*.py"):
            txt = tp.read_text(encoding="utf-8")
            if needle in txt:
                tcount += len(re.findall(r"^\s*def test_", txt, re.M))
        path = "src/production_agent/" + ("" if d == "(root)" else d + "/")
        out.append({"path": path, "files": len(files), "tests": tcount, "coverage": pct})
    return out


def run_guardian() -> dict:
    env = dict(os.environ)
    env["GUARDIAN_SKIP_D6"] = "1"  # Henne-Ei vermeiden: D6 verlangt gestagte status.json
    r = subprocess.run(
        [sys.executable, str(ROOT / "autopilot" / "guardian.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=env,
    )
    if "GUARDIAN ok" in r.stdout:
        return {"ok": True, "errors": []}
    errs = [ln.strip()[2:] for ln in r.stdout.splitlines() if ln.strip().startswith("- ")]
    return {"ok": False, "errors": errs or [(r.stdout + r.stderr)[-300:]]}


# --- Berechnung (rein, damit testbar) ----------------------------------------------------


def _deps(task: dict, tasks: list[dict]) -> list[str]:
    if "deps" in task:
        return task["deps"]
    g = task.get("group")
    return [t["id"] for t in tasks if t.get("group") == (g - 1)] if g is not None else []


def compute_packages(
    tasks: list[dict],
    journal: list[dict],
    commits: list[dict],
    tags: set[str],
    sync_ids: set[str],
    special_done: dict[str, bool],
) -> list[dict]:
    """Fortschritt je Paket: Gate grün 40, Review pass 30, Commit mit Scope 20, Tag wp/<id> 10."""
    packages: list[dict] = []
    for task in tasks:
        tid = task["id"]
        pkg_commits = [c for c in commits if c["scope"] == tid]
        entries = [e for e in journal if e.get("wp") == tid]
        if tid in special_done:
            done = special_done[tid]
            percent = 100 if done else 0
            state = "fertig" if done else "offen"
            steps = [{"name": n, "done": done, "at": None} for n in STEP_NAMES]
        else:
            gate = any(e.get("ok") for e in entries)
            reviews = [
                e["review"]["verdict"]
                for e in entries
                if e.get("review") and e["review"].get("verdict")
            ]
            review_pass = "pass" in reviews
            blocked = bool(reviews) and reviews[-1] in ("fail", "escalate")
            has_commit = bool(pkg_commits)
            has_tag = tid in tags
            percent = (
                (40 if gate else 0)
                + (30 if review_pass else 0)
                + (20 if has_commit else 0)
                + (10 if has_tag else 0)
            )
            if blocked:
                state = "blockiert"
            elif has_commit:
                state = "fertig"
            elif review_pass:
                state = "review_pass"
            elif gate:
                state = "gate_grün"
            elif entries:
                state = "läuft"
            else:
                state = "offen"
            steps = [
                {"name": "Gate grün", "done": gate, "at": _first(entries, lambda e: e.get("ok"))},
                {
                    "name": "Review",
                    "done": review_pass,
                    "at": _first(
                        entries,
                        lambda e: (e.get("review") or {}).get("verdict") == "pass",
                    ),
                },
                {
                    "name": "Commit",
                    "done": has_commit,
                    "at": pkg_commits[0]["at"] if pkg_commits else None,
                },
                {"name": "Tag", "done": has_tag, "at": None},
                {"name": "Sync-Paket", "done": tid in sync_ids, "at": None},
            ]
        packages.append(
            {
                "id": tid,
                "name": task.get("name", tid),
                "agent": task.get("agent", ""),
                "deps": _deps(task, tasks),
                "percent": percent,
                "state": state,
                "steps": steps,
                "attempts": len(entries),
                "cost_usd": round(sum((e.get("cost_usd") or 0) for e in entries), 2),
                "last_at": entries[-1].get("at") if entries else None,
                "commits": [
                    {"sha": c["sha"][:7], "title": c["title"], "at": c["at"]} for c in pkg_commits
                ],
            }
        )
    return packages


def _first(entries: list[dict], pred) -> str | None:
    for e in entries:
        if pred(e):
            return e.get("at")
    return None


def build_timeline(commits: list[dict], journal: list[dict], tags: set[str]) -> list[dict]:
    tl: list[dict] = []
    for c in commits:
        tl.append({"at": c["at"], "kind": "commit", "ref": c["sha"][:7], "text": c["title"]})
    for e in journal:
        at = e.get("at", "")
        wp = e.get("wp", "")
        tl.append(
            {
                "at": at,
                "kind": "journal",
                "ref": wp,
                "text": f"{wp} {'ok' if e.get('ok') else 'offen'} ({e.get('attempts', '?')} Versuche)",
            }
        )
        if e.get("review"):
            tl.append(
                {
                    "at": at,
                    "kind": "review",
                    "ref": wp,
                    "text": f"Review {e['review'].get('verdict', '?')}",
                }
            )
    for t in sorted(tags):
        tl.append({"at": "", "kind": "tag", "ref": f"wp/{t}", "text": f"Tag wp/{t}"})
    tl.sort(key=lambda x: x["at"] or "", reverse=True)
    return tl


def build_status(
    *,
    packages: list[dict],
    journal: list[dict] | None = None,
    commits: list[dict] | None = None,
    tags: set[str] | None = None,
    coverage: dict | None = None,
    tests: int = 0,
    structure: list[dict] | None = None,
    guardian: dict | None = None,
    commit: str = "",
    branch: str = "main",
    generated_at: str | None = None,
) -> dict:
    journal = journal or []
    percents = [p["percent"] for p in packages]
    totals = {
        "percent": round(sum(percents) / len(percents)) if percents else 0,
        "hours_agent": round(sum((e.get("minutes") or 0) for e in journal) / 60, 2),
        "cost_usd": round(sum((e.get("cost_usd") or 0) for e in journal), 2),
        "tests": tests,
        "coverage_total": (coverage or {}).get("total"),
        "coverage_security": (coverage or {}).get("security"),
    }
    return {
        "generated_at": generated_at or datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "commit": commit,
        "branch": branch,
        "packages": packages,
        "totals": totals,
        "timeline": build_timeline(commits or [], journal, tags or set()),
        "guardian": guardian or {"ok": True, "errors": []},
        "structure": structure or [],
    }


# --- HTML (statisch, ohne Frameworks, JSON inline) ---------------------------------------

STATE_COLOR = {
    "offen": "#9aa5ab",
    "läuft": "#005a64",
    "gate_grün": "#006252",
    "review_pass": "#006252",
    "fertig": "#679881",
    "blockiert": "#5d0a1f",
}


def _bar(pct, color="#0b4f6c"):
    pct = pct if pct is not None else 0
    return (
        f'<div class="bar"><div class="fill" style="width:{pct}%;background:{color}"></div>'
        f"<span>{pct}%</span></div>"
    )


def render_html(st: dict) -> str:
    data = json.dumps(st, ensure_ascii=False).replace("</", "<\\/")
    t = st["totals"]
    g = st["guardian"]
    tiles = "".join(
        f'<div class="tile"><b>{v}</b><span>{k}</span></div>'
        for k, v in [
            ("Tests", t["tests"]),
            ("Coverage", f"{t['coverage_total']}%" if t["coverage_total"] is not None else "—"),
            (
                "Coverage security",
                f"{t['coverage_security']}%" if t["coverage_security"] is not None else "—",
            ),
            ("Agentenstunden", t["hours_agent"]),
            ("Kosten (USD)", t["cost_usd"]),
            ("Guardian", "ok" if g["ok"] else "FEHLER"),
        ]
    )
    rows = ""
    for p in st["packages"]:
        markers = " ".join(
            f'<span class="m {"on" if s["done"] else ""}" title="{s["name"]}">{s["name"][0]}</span>'
            for s in p["steps"]
        )
        rows += (
            f"<tr><td>{p['id']}</td><td>{p['agent']}</td>"
            f"<td>{_bar(p['percent'], STATE_COLOR.get(p['state'], '#0b4f6c'))}</td>"
            f'<td><span class="state" style="color:{STATE_COLOR.get(p["state"], "#0b4f6c")}">{p["state"]}</span></td>'
            f"<td>{markers}</td></tr>"
        )
    struct = "".join(
        f"<tr><td>{s['path']}</td><td>{s['files']}</td><td>{s['tests']}</td>"
        f"<td>{_bar(s['coverage'], '#005a64')}</td></tr>"
        for s in st["structure"]
    )
    timeline = "".join(
        f'<li><span class="k">{e["kind"]}</span> <span class="at">{e["at"]}</span> '
        f"{e['ref']} — {e['text']}</li>"
        for e in st["timeline"]
    )
    return f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8">
<title>Production Agent – Projektstatus</title>
<style>
:root{{--teal:#0b4f6c;--teal2:#005a64;--teal3:#006252;--wine:#5d0a1f;--green:#679881}}
body{{font-family:system-ui,sans-serif;margin:0;color:#12313c;background:#f4f7f8}}
header{{background:var(--teal);color:#fff;padding:18px 24px}}
header h1{{margin:0 0 6px;font-size:20px}} header .meta{{opacity:.85;font-size:13px}}
main{{padding:20px 24px;max-width:1100px;margin:0 auto}}
.bar{{position:relative;background:#dde5e8;border-radius:4px;height:18px;min-width:120px}}
.bar .fill{{height:100%;border-radius:4px}}
.bar span{{position:absolute;left:6px;top:0;font-size:11px;line-height:18px;color:#12313c}}
.tiles{{display:flex;flex-wrap:wrap;gap:12px;margin:16px 0}}
.tile{{background:#fff;border:1px solid #dde5e8;border-radius:8px;padding:12px 16px;min-width:120px}}
.tile b{{display:block;font-size:22px;color:var(--teal2)}} .tile span{{font-size:12px;color:#5a6b72}}
table{{width:100%;border-collapse:collapse;background:#fff;border:1px solid #dde5e8;border-radius:8px;overflow:hidden}}
th,td{{text-align:left;padding:8px 10px;border-bottom:1px solid #eef2f3;font-size:13px;vertical-align:middle}}
th{{background:var(--teal3);color:#fff;font-weight:600}}
.state{{font-weight:600}}
.m{{display:inline-block;width:18px;height:18px;line-height:18px;text-align:center;border-radius:4px;
   background:#dde5e8;color:#5a6b72;font-size:11px}}
.m.on{{background:var(--green);color:#fff}}
h2{{font-size:15px;margin:22px 0 8px;color:var(--teal)}}
ul.timeline{{list-style:none;padding:0;margin:0}}
ul.timeline li{{background:#fff;border:1px solid #dde5e8;border-radius:6px;padding:6px 10px;margin-bottom:6px;font-size:13px}}
ul.timeline .k{{display:inline-block;min-width:70px;color:var(--teal2);font-weight:600}}
ul.timeline .at{{color:#5a6b72;font-size:12px}}
</style></head>
<body>
<script id="data" type="application/json">{data}</script>
<header>
  <h1>Production Agent – Projektstatus</h1>
  <div class="meta">Stand {st["generated_at"]} · Commit {st["commit"][:7] or "—"} · Branch {st["branch"]}</div>
  <div style="margin-top:10px;max-width:420px">{_bar(t["percent"], "#679881")}</div>
</header>
<main>
  <div class="tiles">{tiles}</div>
  <h2>Arbeitspakete</h2>
  <table><tr><th>WP</th><th>Agent</th><th>Fortschritt</th><th>Status</th><th>Schritte (G R C T S)</th></tr>{rows}</table>
  <h2>Projektstruktur (src/)</h2>
  <table><tr><th>Pfad</th><th>Dateien</th><th>Tests</th><th>Coverage</th></tr>{struct}</table>
  <h2>Zeitleiste (neueste zuerst)</h2>
  <ul class="timeline">{timeline}</ul>
</main>
</body></html>
"""


# --- Auto-Marker in Doku (gegen veraltete Zahlen) ----------------------------------------

MARKER_FILES = ["README.md", "docs/guardian.md", "docs/test_strategy.md"]


def parse_guardian_rules() -> list[tuple[str, str]]:
    """Liest die Regelliste aus dem Docstring von guardian.py (eine Zeile je Regel)."""
    text = (ROOT / "autopilot" / "guardian.py").read_text(encoding="utf-8")
    m = re.search(r'"""(.*?)"""', text, re.S)
    doc = m.group(1) if m else ""
    rules: list[tuple[str, str]] = []
    for line in doc.splitlines():
        mm = re.match(r"\s*([SKD]\d{1,2}[a-z]?)\s{2,}(.+?)\s*$", line)
        if mm:
            rules.append((mm.group(1), mm.group(2)))
    return rules


def _rule_ranges(rules: list[tuple[str, str]]) -> str:
    def hi(prefix: str) -> int:
        nums = [
            int(re.match(rf"{prefix}(\d{{1,2}})", r).group(1))
            for r, _ in rules
            if r.startswith(prefix)
        ]
        return max(nums) if nums else 0

    return f"S1–S{hi('S')}, K1–K{hi('K')}, D1–D{hi('D')}"


def _hook_names() -> list[str]:
    cfg = yaml.safe_load((ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    names: list[str] = []
    for repo in cfg.get("repos", []):
        for h in repo.get("hooks", []):
            names.append(h.get("name") or h.get("id"))
    return names


def marker_values() -> dict[str, str]:
    """Alle Marker-Werte aus Fakten berechnet – Quelle der Wahrheit für D7."""
    cov = read_coverage()
    tests = pytest_count()
    tools = (
        (ROOT / "src/production_agent/mcp/mes_server.py")
        .read_text(encoding="utf-8")
        .count("@mcp.tool")
    )
    tasks_yaml = yaml.safe_load((ROOT / "autopilot" / "tasks.yaml").read_text(encoding="utf-8"))
    journal = read_journal()
    commits = gather_commits()
    tags = gather_tags()
    sync_dir = ROOT / "autopilot" / "sync"
    sync_ids = {p.stem for p in sync_dir.glob("*.md")} if sync_dir.exists() else set()
    scopes = {c["scope"] for c in commits}
    special_done = {
        "P": (ROOT / "docs/plan.md").exists() and "P" in scopes,
        "A": (ROOT / "docs/architecture.md").exists() and "A" in scopes,
        "WP0": (ROOT / "docs/adr/0001-ereignisdefinition.md").exists() and "WP0" in scopes,
    }
    specials = [
        {"id": "P", "name": "Planung", "agent": "—", "deps": []},
        {"id": "A", "name": "Architektur", "agent": "—", "deps": ["P"]},
        {"id": "WP0", "name": "Entscheidungsbasis", "agent": "—", "deps": ["A"]},
    ]
    pkgs = compute_packages(specials + tasks_yaml, journal, commits, tags, sync_ids, special_done)
    done = [p for p in pkgs if p["state"] == "fertig"]
    openp = [p for p in pkgs if p["state"] != "fertig"]
    total = round(sum(p["percent"] for p in pkgs) / len(pkgs)) if pkgs else 0
    rules = parse_guardian_rules()
    rules_md = f"Regeln: {_rule_ranges(rules)}.\n\n" + "\n".join(
        f"- **{r}**: {t}" for r, t in rules
    )
    lc = commits[0] if commits else None
    stand = (
        f"- fertig: {len(done)} von {len(pkgs)} Paketen\n"
        f"- offen: {', '.join(p['id'] for p in openp) or '—'}\n"
        f"- Fortschritt: {total} % — siehe [Statusseite](docs/status/index.html)"
    )
    return {
        "tests": str(tests),
        "coverage_total": f"{cov['total']} %" if cov else "—",
        "coverage_security": f"{cov['security']} %" if cov and cov["security"] is not None else "—",
        "guardian_rules": rules_md,
        "tools_mes": str(tools),
        "packages_open": str(len(openp)),
        "packages_done": str(len(done)),
        "stand": stand,
        "hooks": "\n".join(f"- {h}" for h in _hook_names()),
        "last_commit": f"{lc['sha'][:7]} ({lc['at'][:10]})" if lc else "—",
    }


def apply_markers(text: str, values: dict[str, str]) -> str:
    """Ersetzt <!-- auto:key -->…<!-- /auto:key --> im Text durch die berechneten Werte (rein, testbar)."""
    for key, val in values.items():
        pat = re.compile(rf"(<!-- auto:{key} -->)(.*?)(<!-- /auto:{key} -->)", re.S)
        sep = "\n" if "\n" in val else ""
        text = pat.sub(lambda m, v=val, s=sep: f"{m.group(1)}{s}{v}{s}{m.group(3)}", text)
    return text


def fill_markers(stage: bool, values: dict[str, str] | None = None) -> list[str]:
    """Füllt die auto-Marker in MARKER_FILES; staged die geänderten Dateien (für den Hook)."""
    vals = values if values is not None else marker_values()
    changed: list[str] = []
    for rel in MARKER_FILES:
        p = ROOT / rel
        if not p.exists():
            continue
        orig = p.read_text(encoding="utf-8")
        txt = apply_markers(orig, vals)
        if txt != orig:
            p.write_text(txt, encoding="utf-8")
            changed.append(rel)
    if stage and changed:
        subprocess.run(["git", "add", *changed], cwd=ROOT)
    return changed


# --- Orchestrierung ----------------------------------------------------------------------


def _doc_summary(path: Path) -> tuple[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    heading = next((ln.lstrip("# ").strip() for ln in lines if ln.startswith("#")), path.stem)
    para = next((ln.strip() for ln in lines if ln.strip() and not ln.startswith(("#", "<!--"))), "")
    desc = re.sub(r"\s+", " ", para)[:140]
    desc = re.sub(
        r"\d+\s+(Tests?|Werkzeuge?)", "…", desc
    )  # D8-Muster in Beschreibungen neutralisieren
    desc = re.sub(r"[SKD]1\s*[–-]\s*[SKD]\d", "…", desc)
    desc = re.sub(r"\d+\s*%", "…", desc)
    return heading, desc


def build_docs_index(stage: bool) -> None:
    """docs/index.md aus allen docs/**/*.md erzeugen (Guardian D11)."""
    docs = ROOT / "docs"
    sections: dict[str, list[str]] = {name: [] for name, _ in DOC_SECTIONS}
    sections["Weiteres"] = []
    for p in sorted(docs.rglob("*.md")):
        if p.name == "index.md":
            continue
        rel = p.relative_to(docs).as_posix()
        heading, desc = _doc_summary(p)
        line = f"- [{rel}]({rel}) – {heading}" + (f": {desc}" if desc else "")
        target = next((name for name, pred in DOC_SECTIONS if pred(rel)), "Weiteres")
        sections[target].append(line)
    parts = [
        "# Doku-Index",
        "Automatisch erzeugt von autopilot/status.py – nicht von Hand pflegen.",
    ]
    for name in [n for n, _ in DOC_SECTIONS] + ["Weiteres"]:
        if sections[name]:
            parts.append(f"## {name}\n" + "\n".join(sections[name]))
    (docs / "index.md").write_text("\n\n".join(parts) + "\n", encoding="utf-8")
    if stage:
        subprocess.run(["git", "add", "docs/index.md"], cwd=ROOT)


def write_files(st: dict) -> None:
    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    (STATUS_DIR / "status.json").write_text(
        json.dumps(st, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (STATUS_DIR / "index.html").write_text(render_html(st), encoding="utf-8")


def generate(stage: bool = False, run_guardian_check: bool = False) -> dict:
    tasks_yaml = yaml.safe_load((ROOT / "autopilot" / "tasks.yaml").read_text(encoding="utf-8"))
    journal = read_journal()
    commits = gather_commits()
    tags = gather_tags()
    sync_dir = ROOT / "autopilot" / "sync"
    sync_ids = {p.stem for p in sync_dir.glob("*.md")} if sync_dir.exists() else set()
    scopes = {c["scope"] for c in commits}
    special_done = {
        "P": (ROOT / "docs/plan.md").exists() and "P" in scopes,
        "A": (ROOT / "docs/architecture.md").exists() and "A" in scopes,
        "WP0": (ROOT / "docs/adr/0001-ereignisdefinition.md").exists() and "WP0" in scopes,
    }
    specials = [
        {"id": "P", "name": "Planung", "agent": "—", "deps": []},
        {"id": "A", "name": "Architektur", "agent": "—", "deps": ["P"]},
        {"id": "WP0", "name": "Entscheidungsbasis", "agent": "—", "deps": ["A"]},
    ]
    tasks_all = specials + tasks_yaml
    coverage = read_coverage()
    st = build_status(
        packages=compute_packages(tasks_all, journal, commits, tags, sync_ids, special_done),
        journal=journal,
        commits=commits,
        tags=tags,
        coverage=coverage,
        tests=pytest_count(),
        structure=gather_structure(coverage),
        guardian=run_guardian() if run_guardian_check else {"ok": True, "errors": []},
        commit=head_sha(),
        branch=branch(),
    )
    write_files(st)
    fill_markers(stage)
    build_docs_index(stage)
    try:
        import present  # noqa: PLC0415

        present.generate(stage=stage)
    except Exception as exc:  # noqa: BLE001
        print(f"WARN present.py: {exc}", file=sys.stderr)
    if stage:
        subprocess.run(
            ["git", "add", "docs/status/status.json", "docs/status/index.html"], cwd=ROOT
        )
    return st


def check() -> int:
    generate(stage=True)  # frisch erzeugen und stagen, dann prüfen
    sj = STATUS_DIR / "status.json"
    if not sj.exists():
        print("status.json fehlt")
        return 1
    data = json.loads(sj.read_text(encoding="utf-8"))
    try:
        ts = datetime.fromisoformat(data["generated_at"])
    except (KeyError, ValueError):
        print("status.json generated_at unlesbar")
        return 1
    age = (datetime.now() - ts).total_seconds()
    if age > 600:
        print(f"status.json ist {int(age // 60)} min alt (>10)")
        return 1
    print(
        f"status.json aktuell: {data['totals']['percent']}% gesamt, "
        f"{len(data['packages'])} Pakete, Commit {data['commit'][:7] or '—'}"
    )
    return 0


if __name__ == "__main__":
    if "--check" in sys.argv:
        sys.exit(check())
    if "--json" in sys.argv:
        st = generate(stage=False)
        print(json.dumps(st, ensure_ascii=False, indent=2))
        sys.exit(0)
    st = generate(stage="--stage" in sys.argv, run_guardian_check="--stage" not in sys.argv)
    print(STATUS_DIR / "status.json")
    print(STATUS_DIR / "index.html")
