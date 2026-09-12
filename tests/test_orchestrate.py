"""Orchestrator: Scheduler-Kern (rein) und Rundenablauf mit Fake-Runner (kein Git, kein Subprozess)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "autopilot"))

import orchestrate  # noqa: E402

PLAN = {
    "lanes": {"steef": {}, "data": {}, "mcp": {}, "graph": {}},
    "packages": [
        {"id": "WP0", "lane": "steef", "deps": []},
        {"id": "WP1", "lane": "data", "deps": ["WP0"]},
        {"id": "WP2a", "lane": "mcp", "deps": ["WP0"]},
        {"id": "WP2b", "lane": "mcp", "deps": ["WP2a"]},
        {"id": "WP3", "lane": "graph", "deps": ["WP2a"]},
        {"id": "WP4", "lane": "graph", "deps": ["WP1", "WP3"]},
    ],
}


class FakeRunner:
    def __init__(self, escalate=(), budget_stop=False):
        self.escalate = set(escalate)
        self.budget_stop = budget_stop
        self.merged: list[str] = []
        self.tagged: list[str] = []

    def budget_ok(self, state):
        return not self.budget_stop

    def run_wp(self, wp, state):
        state["wp"][wp]["loops"] += 1
        state["wp"][wp]["status"] = "escalated" if wp in self.escalate else "review_pass"

    def merge_wp(self, wp, state):
        state["wp"][wp]["status"] = "merged"
        self.merged.append(wp)
        self.tagged.append(wp)

    def push(self, state):
        pass


class QuotaRunner:
    """Fake, der bei bestimmten WPs eine Quota (429) meldet – ohne Loop zu verbrauchen."""

    def __init__(self, quota_times: dict | None = None, persist: bool = False):
        self.quota_times = dict(quota_times or {})
        self.persist = persist
        self.merged: list[str] = []

    def budget_ok(self, state):
        return True

    def run_wp(self, wp, state):
        if self.persist or self.quota_times.get(wp, 0) > 0:
            if not self.persist:
                self.quota_times[wp] -= 1
            state["_quota"] = True
            state["wp"][wp]["status"] = "quota"  # kein loops += 1
            return
        state["wp"][wp]["loops"] += 1
        state["wp"][wp]["status"] = "review_pass"

    def merge_wp(self, wp, state):
        state["wp"][wp]["status"] = "merged"
        self.merged.append(wp)

    def push(self, state):
        pass


def _state():
    return orchestrate.init_state(PLAN, 40.0, "test")


def test_quota_pauses_then_resumes_without_loop_consumption(tmp_path, monkeypatch):
    monkeypatch.setattr(orchestrate, "STATE_PATH", tmp_path / "o.json")
    runner = QuotaRunner({"WP1": 1})  # WP1 einmal Quota, dann normal
    slept = []
    rc = orchestrate.orchestrate(
        PLAN, _state(), runner, quota_interval=900, sleep=lambda s: slept.append(s)
    )
    assert rc == 0
    assert "WP1" in runner.merged and slept  # pausiert und danach fortgesetzt
    st = orchestrate.load_state(PLAN, 40.0, "test")
    assert st["wp"]["WP1"]["loops"] == 1  # Quota hat keinen Loop verbraucht


def test_persistent_quota_exits_3_falsification(tmp_path, monkeypatch):
    monkeypatch.setattr(orchestrate, "STATE_PATH", tmp_path / "o.json")
    runner = QuotaRunner(persist=True)
    rc = orchestrate.orchestrate(
        PLAN, _state(), runner, quota_wait_hours=0.001, quota_interval=1, sleep=lambda s: None
    )
    assert rc == 3 and runner.merged == []


def test_wp1_and_wp2a_start_concurrently():
    ready = orchestrate.ready_packages(_state(), PLAN)
    assert "WP1" in ready and "WP2a" in ready  # verschiedene Lanes, deps WP0 merged


def test_wp3_only_ready_after_wp2a_merged():
    st = _state()
    assert "WP3" not in orchestrate.startable(st, PLAN)
    st["wp"]["WP2a"]["status"] = "merged"
    assert "WP3" in orchestrate.startable(st, PLAN)


def test_merged_is_skipped():
    st = _state()
    st["wp"]["WP1"]["status"] = "merged"
    assert "WP1" not in orchestrate.startable(st, PLAN)


def test_state_survives_restart(tmp_path, monkeypatch):
    monkeypatch.setattr(orchestrate, "STATE_PATH", tmp_path / "orchestrator.json")
    st = _state()
    st["wp"]["WP1"]["status"] = "merged"
    orchestrate.save_state(st)
    reloaded = orchestrate.load_state(PLAN, 40.0, "test")
    assert reloaded["wp"]["WP1"]["status"] == "merged"


def test_two_ready_wps_merged_in_order_and_tagged(tmp_path, monkeypatch):
    monkeypatch.setattr(orchestrate, "STATE_PATH", tmp_path / "orchestrator.json")
    runner = FakeRunner()
    rc = orchestrate.orchestrate(PLAN, _state(), runner)
    assert rc == 0
    assert set(runner.merged) == {"WP1", "WP2a", "WP2b", "WP3", "WP4"}
    assert runner.merged.index("WP2a") < runner.merged.index("WP3")  # dep vor abhängigem
    assert runner.tagged == runner.merged


def test_escalated_blocks_dependents_but_siblings_continue(tmp_path, monkeypatch):
    monkeypatch.setattr(orchestrate, "STATE_PATH", tmp_path / "orchestrator.json")
    runner = FakeRunner(escalate={"WP3"})
    rc = orchestrate.orchestrate(PLAN, _state(), runner)
    assert rc == 2  # nicht alles merged
    st = orchestrate.load_state(PLAN, 40.0, "test")
    assert st["wp"]["WP3"]["status"] == "escalated"
    assert st["wp"]["WP4"]["status"] != "merged"  # dep WP3 eskaliert → blockiert
    assert st["wp"]["WP2b"]["status"] == "merged"  # anderer Strang läuft weiter


def test_budget_exhausted_starts_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(orchestrate, "STATE_PATH", tmp_path / "orchestrator.json")
    runner = FakeRunner(budget_stop=True)
    rc = orchestrate.orchestrate(PLAN, _state(), runner)
    assert rc == 2 and runner.merged == []


def test_cycle_is_k6_error_falsification():
    assert orchestrate.deps_cycle({"A": ["B"], "B": ["A"]})
    bad_plan = {"packages": [{"id": "A", "deps": ["B"]}, {"id": "B", "deps": ["A"]}]}
    assert any("K6" in e and "zyklus" in e.lower() for e in orchestrate.check_plan(set(), bad_plan))


def _gate_no_cov_ok(gate: str) -> bool:
    """Ein Gate ist ok, wenn es kein pytest ruft oder jeder pytest-Aufruf --no-cov trägt."""
    return "pytest" not in gate or "--no-cov" in gate


def test_all_pytest_gates_use_no_cov():
    import yaml

    tasks = yaml.safe_load((ROOT / "autopilot" / "tasks.yaml").read_text(encoding="utf-8"))
    for t in tasks:
        assert _gate_no_cov_ok(t["gate"]), f"{t['id']}: pytest-Gate ohne --no-cov"


def test_gate_without_no_cov_is_red_falsification():
    assert _gate_no_cov_ok("pytest tests/test_x.py -q") is False
    assert _gate_no_cov_ok("pytest tests/test_x.py -q --no-cov") is True
    assert _gate_no_cov_ok("make lint test") is True


def test_orchestrate_run_flags_are_covered_by_run_help():
    """Jedes run.py-Flag, das orchestrate.py --dry-run ausgibt, muss run.py --help kennen."""
    import re
    import subprocess

    dry = subprocess.run(
        [sys.executable, "autopilot/orchestrate.py", "--dry-run"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    ).stdout
    help_txt = subprocess.run(
        [sys.executable, "autopilot/run.py", "--help"], cwd=ROOT, capture_output=True, text=True
    ).stdout
    invocations = re.findall(r"run\.py[^\n]*", dry)
    used = set(re.findall(r"--[a-z][a-z-]+", " ".join(invocations)))
    assert used, "dry-run nennt keine run.py-Befehle"
    for flag in used:
        assert flag in help_txt, f"{flag} fehlt in run.py --help"


def test_heal_loop_bounded_no_infinite_loop(monkeypatch):
    """Bleibt der Fix erfolglos, heilt der Orchestrator höchstens max_heal_rounds-mal, dann escalated."""
    monkeypatch.setattr(orchestrate, "save_state", lambda s: None)
    r = orchestrate.Runner(PLAN, heal=True, max_heal_rounds=2)
    calls = {"n": 0}

    def fake_heal_wp(wp, state):
        calls["n"] += 1
        state["wp"][wp]["status"] = "escalated"  # Fix schlägt fehl

    monkeypatch.setattr(r, "heal_wp", fake_heal_wp)
    state = orchestrate.init_state(PLAN, 40.0, "t")
    state["wp"]["WP1"]["status"] = "escalated"
    r._heal_loop("WP1", state)
    assert calls["n"] == 2
    assert state["wp"]["WP1"]["status"] == "escalated"


def test_heal_loop_recovers_after_first_round(monkeypatch):
    monkeypatch.setattr(orchestrate, "save_state", lambda s: None)
    r = orchestrate.Runner(PLAN, heal=True, max_heal_rounds=2)
    calls = {"n": 0}

    def fake_heal_wp(wp, state):
        calls["n"] += 1
        state["wp"][wp]["status"] = "review_pass"

    monkeypatch.setattr(r, "heal_wp", fake_heal_wp)
    state = orchestrate.init_state(PLAN, 40.0, "t")
    state["wp"]["WP1"]["status"] = "escalated"
    r._heal_loop("WP1", state)
    assert calls["n"] == 1
    assert state["wp"]["WP1"]["status"] == "review_pass"


def test_selfheal_autopilot_recovers_after_fix():
    calls = {"gate": 0, "fix": 0}

    def gate():
        calls["gate"] += 1
        return 0 if calls["fix"] >= 1 else 1

    assert orchestrate.selfheal_autopilot(
        gate, lambda i: calls.__setitem__("fix", calls["fix"] + 1), rounds=2, log=lambda *_: None
    )
    assert calls["fix"] == 1


def test_selfheal_autopilot_escalates_after_rounds_falsification():
    calls = {"fix": 0}
    ok = orchestrate.selfheal_autopilot(
        lambda: 1,
        lambda i: calls.__setitem__("fix", calls["fix"] + 1),
        rounds=2,
        log=lambda *_: None,
    )
    assert ok is False
    assert calls["fix"] == 2  # gedeckelt: kein Endlos-Heilen
