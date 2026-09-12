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


def _state():
    return orchestrate.init_state(PLAN, 40.0, "test")


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
