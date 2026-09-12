#!/usr/bin/env python3
"""Orchestrator: ein Befehl baut alle Pakete spezifikationsbasiert, parallel je Lane, bis zum Ende.

Fertig bleibt fertig (merged wird nie wieder angefasst); ein eskalierter Strang blockiert nur seine
Abhängigen, die anderen Lanes laufen weiter. Zustand in autopilot/state/orchestrator.json überlebt
Neustart (Start = Fortsetzung). Der Scheduler-Kern ist rein und testbar; Worktrees, Subprozesse,
Merge und Guardian stecken in einem injizierbaren Runner (Tests ersetzen ihn durch einen Fake).

  python autopilot/orchestrate.py --dry-run              Lanes, startbereite WPs, Befehle
  python autopilot/orchestrate.py --push                 baut und pusht nach jedem Merge
  python autopilot/orchestrate.py --retry WP3            eskaliertes/erschöpftes WP neu einreihen
  python autopilot/orchestrate.py --skip WP5             WP als von-Hand-erledigt markieren
  python autopilot/orchestrate.py --budget-total-usd 60  Budget-Obergrenze (Standard 40)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PLAN_PATH = ROOT / "autopilot" / "plan.yaml"
TASKS_PATH = ROOT / "autopilot" / "tasks.yaml"
STATE_PATH = ROOT / "autopilot" / "state" / "orchestrator.json"
ESCALATION_PATH = ROOT / "ESCALATION.md"

STEEF_LANE = "steef"  # P/A/WP0 – von Stefan, gelten als Voraussetzung (merged)
DONE = "merged"
NEEDS_RETRY = ("exhausted", "escalated")
NOT_STARTABLE = (DONE, "running", "gate_green", "review_pass", "quota", *NEEDS_RETRY)


# --- Plan / reine Helfer (testbar) -------------------------------------------------------


def load_plan(path: Path = PLAN_PATH) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_tasks(path: Path = TASKS_PATH) -> list[dict]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def pkg_map(plan: dict) -> dict[str, dict]:
    return {p["id"]: p for p in plan["packages"]}


def buildable(plan: dict) -> list[str]:
    """Vom Autopilot baubare Pakete (alle außer der steef-Lane P/A/WP0)."""
    return [p["id"] for p in plan["packages"] if p["lane"] != STEEF_LANE]


def deps_cycle(pkgs: dict[str, list[str]]) -> list[str]:
    """Gibt einen Abhängigkeitszyklus als Pfad zurück (leer = azyklisch)."""
    WHITE, GREY, BLACK = 0, 1, 2
    color = dict.fromkeys(pkgs, WHITE)
    path: list[str] = []

    def visit(node: str) -> list[str]:
        color[node] = GREY
        path.append(node)
        for dep in pkgs.get(node, []):
            if dep not in color:
                continue
            if color[dep] == GREY:
                return path[path.index(dep) :] + [dep]
            if color[dep] == WHITE:
                found = visit(dep)
                if found:
                    return found
        color[node] = BLACK
        path.pop()
        return []

    for n in pkgs:
        if color[n] == WHITE:
            found = visit(n)
            if found:
                return found
    return []


def check_plan(tasks_ids: set[str], plan: dict) -> list[str]:
    """K6: jede tasks.yaml-WP steht in plan.yaml, alle deps sind auflösbar und azyklisch."""
    errs: list[str] = []
    ids = {p["id"] for p in plan["packages"]}
    for tid in sorted(tasks_ids - ids):
        errs.append(f"K6 WP {tid} in tasks.yaml, aber nicht in plan.yaml")
    deps = {p["id"]: p.get("deps", []) for p in plan["packages"]}
    for pid, ds in deps.items():
        for d in ds:
            if d not in ids:
                errs.append(f"K6 unbekannte Abhängigkeit {d} von {pid}")
    cyc = deps_cycle(deps)
    if cyc:
        errs.append("K6 Abhängigkeitszyklus: " + " → ".join(cyc))
    return errs


def _status(state: dict, pid: str) -> str:
    return state["wp"].get(pid, {}).get("status", "pending")


def startable(state: dict, plan: dict) -> list[str]:
    """Alle Pakete, deren deps merged sind und die nicht blockiert/fertig/laufend sind (ohne Lane-Grenze)."""
    pkgs = pkg_map(plan)
    out: list[str] = []
    for pid in buildable(plan):
        if _status(state, pid) in NOT_STARTABLE:
            continue
        p = pkgs[pid]
        if not all(_status(state, d) == DONE for d in p["deps"]):
            continue
        if any(_status(state, d) in NEEDS_RETRY for d in p["deps"]):
            continue
        out.append(pid)
    return out


def ready_packages(state: dict, plan: dict) -> list[str]:
    """Tatsächlich startbar: startable + Lane frei (max. ein laufendes WP je Lane)."""
    pkgs = pkg_map(plan)
    used_lanes = {p["lane"] for pid, p in pkgs.items() if _status(state, pid) == "running"}
    ready: list[str] = []
    for pid in startable(state, plan):
        lane = pkgs[pid]["lane"]
        if lane in used_lanes:
            continue
        ready.append(pid)
        used_lanes.add(lane)
    return ready


def all_merged(state: dict, plan: dict) -> bool:
    return all(_status(state, pid) == DONE for pid in buildable(plan))


def blocked_packages(state: dict, plan: dict) -> list[str]:
    """Warten auf eine eskalierte/erschöpfte Abhängigkeit (nur zur Anzeige)."""
    out = []
    for pid in buildable(plan):
        if _status(state, pid) in NOT_STARTABLE:
            continue
        p = pkg_map(plan)[pid]
        if any(_status(state, d) in NEEDS_RETRY for d in p["deps"]):
            out.append(pid)
    return out


def init_state(plan: dict, budget_total: float, run_id: str) -> dict:
    """Frischer Zustand: steef-Pakete gelten als merged (Voraussetzung), Rest pending."""
    wp = {}
    for p in plan["packages"]:
        merged = p["lane"] == STEEF_LANE
        wp[p["id"]] = {
            "status": DONE if merged else "pending",
            "lane": p["lane"],
            "loops": 0,
            "cost_usd": 0.0,
            "started_at": None,
            "finished_at": None,
            "merge_sha": None,
            "worktree": None,
            "last_gate_tail": "",
            "last_review": None,
            "history": [],
        }
    return {"run_id": run_id, "budget_total": budget_total, "budget_used": 0.0, "wp": wp}


def load_state(plan: dict, budget_total: float, run_id: str) -> dict:
    if STATE_PATH.exists():
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        for pid in (p["id"] for p in plan["packages"]):  # neue Pakete ergänzen
            state["wp"].setdefault(pid, init_state(plan, budget_total, run_id)["wp"][pid])
        return state
    return init_state(plan, budget_total, run_id)


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# --- Kernablauf (Runner injizierbar) -----------------------------------------------------


def _resume_quota(state: dict, plan: dict) -> None:
    state["_quota"] = False
    for pid in buildable(plan):
        if _status(state, pid) == "quota":
            state["wp"][pid]["status"] = "pending"


def orchestrate(
    plan: dict,
    state: dict,
    runner,
    push: bool = False,
    max_parallel: int = 3,
    quota_wait_hours: float = 8.0,
    quota_interval: int = 900,
    sleep=None,
) -> int:
    """Rundenbasiert: startbereite WPs (max_parallel, eine je freie Lane) starten, dann fertige mergen.
    Quota (429) pausiert ALLE Lanes: alle quota_interval Sekunden erneut versuchen, bis quota_wait_hours
    erreicht sind → Exit 3. Exit 0 = alles merged, 2 = mindestens ein WP wartet."""
    import time as _time

    sleep = sleep or _time.sleep
    waited = 0
    while True:
        if state.get("_quota"):  # Abo-Quote erschöpft → alle Lanes pausiert
            if waited >= quota_wait_hours * 3600:
                _resume_quota(state, plan)
                save_state(state)
                return 3
            sleep(quota_interval)
            waited += quota_interval
            _resume_quota(state, plan)
            continue
        if not runner.budget_ok(state):
            break
        rdy = ready_packages(state, plan)[:max_parallel]
        if not rdy:
            break
        for wp in rdy:
            runner.run_wp(wp, state)
            if state.get("_quota"):  # Quota mitten in der Runde → Rest pausieren
                break
        for wp in rdy:
            if _status(state, wp) == "review_pass":
                runner.merge_wp(wp, state)
                if push and _status(state, wp) == DONE:
                    runner.push(state)
        save_state(state)
    save_state(state)
    return 0 if all_merged(state, plan) else 2


class Runner:
    """Live-Runner: Worktree je WP, Subprozess run.py, Merge auf main mit Guardian-Gate."""

    def __init__(self, plan: dict, push: bool = False, auto_decide: bool = False):
        self.plan = plan
        self.push = push
        self.auto_decide = auto_decide

    def budget_ok(self, state: dict) -> bool:
        return state["budget_used"] < state["budget_total"]

    def _sh(self, *args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess:
        return subprocess.run(args, cwd=cwd, capture_output=True, text=True)  # noqa: S603

    def run_wp(self, wp: str, state: dict) -> None:
        w = state["wp"][wp]
        w["status"] = "running"
        save_state(state)
        worktree = ROOT.parent / f"orch-{wp}"
        branch = f"wp/{wp}"
        self._sh("git", "worktree", "add", "-B", branch, str(worktree), "main")
        (worktree / ".env").write_bytes((ROOT / ".env").read_bytes()) if (
            ROOT / ".env"
        ).exists() else None
        self._sh(sys.executable, "-m", "production_agent.data.simulator", cwd=worktree)
        r = self._sh(
            sys.executable,
            "autopilot/run.py",
            "--only",
            wp,
            "--review",
            "auto",
            "--max-loops",
            "4",
            cwd=worktree,
        )
        import cc  # noqa: PLC0415

        w["last_gate_tail"] = (r.stdout + r.stderr)[-600:]
        w["worktree"] = str(worktree)
        if cc.is_quota(
            r.returncode, r.stdout + r.stderr
        ):  # Abo-Quote erschöpft: pausieren, kein Loop
            w["status"] = "quota"
            state["_quota"] = True
            save_state(state)
            return
        w["loops"] += 1
        w["status"] = "review_pass" if r.returncode == 0 else "escalated"
        if w["status"] == "escalated" and self.auto_decide:
            import decider  # noqa: PLC0415

            spec = next(
                (
                    p.get("spec", {}).get("prompt_ref", "")
                    for p in self.plan["packages"]
                    if p["id"] == wp
                ),
                "",
            )
            d = decider.decide(wp, "Builder-/Reviewer-Eskalation", w["last_gate_tail"], spec)
            w["last_review"] = d
            if d.get("action") == "apply":  # automatisch entschieden – bitte prüfen
                w["status"] = "review_pass"
                w["auto_decided"] = True
        if w["status"] == "escalated":
            self._escalate(wp, w)
        save_state(state)

    def merge_wp(self, wp: str, state: dict) -> None:
        w = state["wp"][wp]
        merge = self._sh(
            "git", "merge", "--no-ff", f"wp/{wp}", "-m", f"merge({wp}): {wp} übernommen"
        )
        if merge.returncode != 0:
            self._sh("git", "merge", "--abort")
            w["status"] = "escalated"
            self._escalate(wp, w, detail="Merge-Konflikt")
            return
        guard = self._sh(sys.executable, "autopilot/guardian.py")
        if guard.returncode != 0:
            self._sh("git", "reset", "--hard", "ORIG_HEAD")
            w["status"] = "escalated"
            self._escalate(wp, w, detail="Guardian rot nach Merge")
            return
        w["merge_sha"] = self._sh("git", "rev-parse", "HEAD").stdout.strip()
        w["status"] = DONE
        self._sh("git", "tag", "-f", f"wp/{wp}")
        self._sh("git", "worktree", "remove", "--force", w["worktree"] or f"../orch-{wp}")

    def push(self, state: dict) -> None:
        self._sh("git", "push", "--tags")
        self._sh("git", "push")

    def _escalate(self, wp: str, w: dict, detail: str = "") -> None:
        with ESCALATION_PATH.open("a", encoding="utf-8") as fh:
            fh.write(
                f"\n## {wp}\n- Status: {w['status']} {('· ' + detail) if detail else ''}\n"
                f"- Gate-Ausgabe:\n```\n{w['last_gate_tail']}\n```\n"
                f"- Sync-Paket: `python autopilot/sync.py {wp}`\n"
            )


def _print_dry_run(plan: dict, state: dict) -> None:
    print("Lanes:", ", ".join(plan["lanes"]))
    rdy = startable(state, plan)
    blocked = blocked_packages(state, plan)
    print("startbereit:", ", ".join(rdy) or "—")
    print("blockiert:", ", ".join(blocked) or "—")
    for wp in rdy:
        print(
            f"  → git worktree add -B wp/{wp} ../orch-{wp} main && "
            f"python autopilot/run.py --only {wp} --review auto --max-loops 4"
        )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--retry", metavar="WP")
    ap.add_argument("--skip", metavar="WP")
    ap.add_argument("--budget-total-usd", type=float, default=40.0)
    ap.add_argument(
        "--auto-decide", action="store_true", help="Rückfragen von decider.py entscheiden lassen"
    )
    ap.add_argument("--max-parallel", type=int, default=3, help="max. gleichzeitig laufende WPs")
    ap.add_argument(
        "--quota-wait-hours", type=float, default=8.0, help="max. Wartezeit bei Quota, dann Exit 3"
    )
    ap.add_argument("--run-id", default="run")
    args = ap.parse_args(argv)

    plan = load_plan()
    tasks_ids = {t["id"] for t in load_tasks()}
    errs = check_plan(tasks_ids, plan)
    if errs:
        print("plan.yaml inkonsistent (K6):")
        for e in errs:
            print(" -", e)
        return 1

    state = load_state(plan, args.budget_total_usd, args.run_id)
    state["budget_total"] = args.budget_total_usd
    if args.retry:
        state["wp"].setdefault(args.retry, {})["status"] = "pending"
        save_state(state)
        print(f"{args.retry} neu eingereiht (pending)")
        return 0
    if args.skip:
        if input(f"{args.skip} als von Hand erledigt markieren? (j/n) ").strip().lower() == "j":
            state["wp"].setdefault(args.skip, {})["status"] = DONE
            save_state(state)
            print(f"{args.skip} als merged markiert")
        return 0
    if args.dry_run:
        _print_dry_run(plan, state)
        return 0 if all_merged(state, plan) else 2

    runner = Runner(plan, push=args.push, auto_decide=args.auto_decide)
    return orchestrate(
        plan,
        state,
        runner,
        push=args.push,
        max_parallel=args.max_parallel,
        quota_wait_hours=args.quota_wait_hours,
    )


if __name__ == "__main__":
    sys.exit(main())
