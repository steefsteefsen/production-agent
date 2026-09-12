#!/usr/bin/env python3
"""Autopilot: führt die Arbeitspakete aus autopilot/tasks.yaml unbeaufsichtigt mit Claude Code aus.

Ablauf je Aufgabe: Prompt aus decisions.yaml rendern → claude -p an den Subagent → Gate ausführen →
bei Fehler Gate-Ausgabe zurückspielen (max. --retries) → Ergebnis in autopilot/status.json (Import im Cockpit).

Voraussetzungen: claude CLI angemeldet (claude auth status), git-Repo initialisiert, pip install -e ".[dev]".
Sicherheit: Rechte kommen aus .claude/settings.json (kein git push, kein rm -rf, keine .env, keine decisions.yaml).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cc  # noqa: E402
import journal  # noqa: E402
import reviewer  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TASKS = ROOT / "autopilot" / "tasks.yaml"
DECISIONS = ROOT / "decisions.yaml"
STATUS = ROOT / "autopilot" / "status.json"
LOGS = ROOT / "autopilot" / "logs"


def render(prompt: str, dec: dict) -> str:
    def lookup(m: re.Match) -> str:
        cur = dec
        for part in m.group(1).split("."):
            cur = cur[part]
        return json.dumps(cur, ensure_ascii=False) if isinstance(cur, list | dict) else str(cur)

    return re.sub(r"\{\{([a-z_.]+)\}\}", lookup, prompt)


def preflight_claude() -> tuple[bool, str]:
    """Vor dem ersten Lauf: claude erreichbar und angemeldet? Sonst klarer Abbruch statt Hänger."""
    for args in (["claude", "--version"], ["claude", "auth", "status"]):
        try:
            r = subprocess.run(
                args,
                cwd=ROOT,
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
                timeout=60,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            return False, f"{' '.join(args)}: {e}"
        if r.returncode != 0:
            return (
                False,
                f"{' '.join(args)} → Exit {r.returncode}: {(r.stdout + r.stderr).strip()[:200]}",
            )
    return True, "ok"


def claude(
    prompt: str,
    agent: str,
    max_turns: int,
    budget: float,
    log: Path,
    timeout: int = 1800,
    api_billing: bool = False,
) -> tuple[int, dict | None]:
    cmd = [
        "claude",
        "-p",
        prompt,
        "--model",
        cc.model("builder"),
        "--append-system-prompt",
        f"Arbeite als Subagent '{agent}' nach .claude/agents/{agent}.md. Schließe mit ruff check . && pytest -q.",
        "--permission-mode",
        "dontAsk",
        "--max-turns",
        str(max_turns),
        "--output-format",
        "json",
    ]
    if api_billing:  # nur mit bewusster API-Abrechnung ein Budget; sonst läuft alles übers Abo
        cmd += ["--max-budget-usd", str(budget)]
    with log.open("a", encoding="utf-8") as fh:
        fh.write(f"\n===== {time.strftime('%H:%M:%S')} claude -p ({agent}) =====\n{prompt}\n")
        try:
            p = subprocess.run(  # noqa: S603
                cmd,
                cwd=ROOT,
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
                timeout=timeout,
                env=cc.env(api_billing),
            )
        except subprocess.TimeoutExpired:
            fh.write(f"\n[TIMEOUT nach {timeout}s – Loop gezählt]\n")
            return 124, {"timeout": True}
        fh.write(p.stdout + "\n" + p.stderr)
        if cc.is_quota(p.returncode, p.stdout + p.stderr):
            fh.write("\n[QUOTA erreicht – pausieren, kein Loop-Verbrauch]\n")
            return 429, {"quota": True}
        out = None
        try:
            out = json.loads(p.stdout)
            fh.write(
                f"\n[cost={out.get('total_cost_usd') or 'abo'} turns={out.get('num_turns')}]\n"
            )
        except json.JSONDecodeError:
            pass
    return p.returncode, out


def gate(cmd: str, log: Path) -> tuple[int, str]:
    p = subprocess.run(cmd, shell=True, cwd=ROOT, capture_output=True, text=True)  # noqa: S602
    with log.open("a", encoding="utf-8") as fh:
        fh.write(f"\n----- gate: {cmd} -> {p.returncode}\n{p.stdout[-4000:]}\n{p.stderr[-4000:]}\n")
    return p.returncode, (p.stdout + p.stderr)[-3000:]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="nur diese WP-IDs")
    ap.add_argument(
        "--max-loops",
        type=int,
        default=4,
        help="Builder-Versuche und Reviewer-fail-Nachbesserungen zusammen (Standard 4)",
    )
    ap.add_argument(
        "--retries",
        type=int,
        default=None,
        help="Alias für --max-loops (retries = max-loops − 1)",
    )
    ap.add_argument(
        "--claude-timeout", type=int, default=1800, help="Timeout je claude-Aufruf in Sekunden"
    )
    ap.add_argument("--max-turns", type=int, default=60)
    ap.add_argument("--budget", type=float, default=4.0, help="USD je Versuch")
    ap.add_argument("--dry-run", action="store_true", help="nur Prompts rendern")
    ap.add_argument(
        "--review",
        choices=["off", "auto", "human", "both"],
        default="auto",
        help="auto: kontextfreier Claude-Reviewer, eskaliert nur bei fail/escalate an dich; human: du; both: beide; off: kein Review",
    )
    ap.add_argument(
        "--review-model",
        default=cc.model("reviewer"),
        help="Modell des Reviewers (Standard aus settings.env)",
    )
    ap.add_argument(
        "--narrate",
        action="store_true",
        help="Journal-Eintrag zusätzlich von Haiku in drei Sätzen erzählen lassen",
    )
    ap.add_argument("--no-commit", action="store_true", help="keinen Commit je WP")
    ap.add_argument(
        "--api-billing",
        action="store_true",
        help="claude bewusst über die API abrechnen (Budget aktiv); Standard ist Abo-Betrieb ohne API-Key",
    )
    args = ap.parse_args()
    max_loops = (args.retries + 1) if args.retries is not None else args.max_loops

    dec = yaml.safe_load(DECISIONS.read_text(encoding="utf-8"))
    tasks = yaml.safe_load(TASKS.read_text(encoding="utf-8"))
    status = (
        json.loads(STATUS.read_text()) if STATUS.exists() else {"wp": {}, "hours": 0, "runs": {}}
    )
    LOGS.mkdir(exist_ok=True)
    if not args.dry_run:
        ready, msg = cc.preflight(args.api_billing)
        if not ready:
            print(f"Abbruch: {msg}")
            return 1
    t_start = time.time()

    for t in tasks:
        if args.only and t["id"] not in args.only:
            continue
        if status["wp"].get(t["id"]):
            print(f"{t['id']} bereits fertig – übersprungen")
            continue
        prompt = render(t["prompt"], dec)
        if args.dry_run:
            print(f"\n### {t['id']} → {t['agent']}\n{prompt}\n--- gate: {t['gate']}")
            continue
        log = LOGS / f"{t['id']}.log"
        ok = False
        t0 = time.time()
        cj = None
        for attempt in range(1, max_loops + 1):
            print(f"{t['id']} Versuch {attempt}/{max_loops} ({t['agent']}) …", flush=True)
            _, cj = claude(
                prompt,
                t["agent"],
                args.max_turns,
                args.budget,
                log,
                args.claude_timeout,
                args.api_billing,
            )
            if cj and cj.get("quota"):
                print(f"{t['id']}: Quota erreicht – Abbruch dieses WP (kein Loop-Verbrauch)")
                out = "Quota erreicht"
                break
            if cj and cj.get("timeout"):
                out = f"Claude-Timeout nach {args.claude_timeout}s (zählt als Loop)"
                print(f"{t['id']}: {out}")
                continue
            rc, out = gate(t["gate"], log)
            if rc == 0:
                ok = True
                break
            prompt = f"{render(t['prompt'], dec)}\n\nDer Abnahmetest ist fehlgeschlagen. Behebe genau das:\n{out}"
        verdict = None
        if ok and args.review in ("auto", "both"):
            verdict = reviewer.review(
                t["id"],
                t.get("review_gate", []),
                t.get("review_files", []),
                out if not ok else "grün",
                args.review_model,
            )
            print(reviewer.format_verdict(verdict))
            if verdict.get("verdict") == "fail":
                fails = "\n".join(
                    f"- {i['check']}: {i['evidence']}"
                    for i in verdict.get("items", [])
                    if i["result"] == "fail"
                )
                print(f"{t['id']}: Reviewer fail – ein Nachbesserungslauf")
                _, cj = claude(
                    f"{render(t['prompt'], dec)}\n\nEin unabhängiger Review hat diese Punkte beanstandet. Behebe genau diese:\n{fails}",
                    t["agent"],
                    args.max_turns,
                    args.budget,
                    log,
                    args.claude_timeout,
                    args.api_billing,
                )
                rc, out = gate(t["gate"], log)
                ok = rc == 0
                if ok:
                    verdict = reviewer.review(
                        t["id"],
                        t.get("review_gate", []),
                        t.get("review_files", []),
                        "grün",
                        args.review_model,
                    )
                    print(reviewer.format_verdict(verdict))
                    ok = verdict.get("verdict") == "pass"
        needs_human = args.review in ("human", "both") or (
            verdict and verdict.get("verdict") == "escalate"
        )
        if ok and needs_human:
            print(f"\nReview-Gate {t['id']} – bitte prüfen:")
            for item in t.get("review_gate", []):
                print(f"  [ ] {item}")
            if verdict and verdict.get("question_for_human"):
                print(f"  Frage des Reviewers: {verdict['question_for_human']}")
            ok = input("Abnehmen? (j/n) ").strip().lower() == "j"
        e = journal.entry(
            t["id"],
            t["agent"],
            attempt,
            ok,
            cj,
            out if not ok else "grün",
            time.time() - t0,
            args.narrate,
        )
        e["review"] = verdict
        journal.write(e)
        if ok and not args.no_commit:
            journal.commit(t["id"], e)
        status["wp"][t["id"]] = ok
        status["runs"][t["id"]] = {
            "attempts": attempt,
            "ok": ok,
            "at": time.strftime("%Y-%m-%d %H:%M"),
        }
        status["hours"] = round((time.time() - t_start) / 3600, 2)
        status["asOf"] = time.strftime("%Y-%m-%d")
        STATUS.write_text(json.dumps(status, indent=2, ensure_ascii=False))
        print(f"{t['id']}: {'OK' if ok else 'FEHLGESCHLAGEN'} – Log: {log}")
        if not ok:
            print(
                "Stopp: Gate rot. Log prüfen, Prompt anpassen, erneut starten (fertige WPs werden übersprungen)."
            )
            return 1
    print("Alle Aufgaben fertig. status.json ins Cockpit importieren.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
