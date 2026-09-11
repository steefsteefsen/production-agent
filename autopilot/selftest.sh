#!/usr/bin/env bash
# Selbsttest des Basisprojekts – ohne API-Key, ohne Commit. Aufruf: bash autopilot/selftest.sh
cd "$(dirname "$0")/.." || exit 1
P=0; F=0
ok(){ echo "PASS  $1"; P=$((P+1)); }
ko(){ echo "FAIL  $1"; F=$((F+1)); }
chk(){ if eval "$2" >/dev/null 2>&1; then ok "$1"; else ko "$1"; fi; }

echo "== Umgebung"
chk "venv aktiv"                         '[ -n "$VIRTUAL_ENV" ]'
chk "python ist venv-python"             '[ "$(command -v python)" = "$VIRTUAL_ENV/bin/python" ]'
chk "Python ≥ 3.11"                      'python -c "import sys;assert sys.version_info>=(3,11)"'
for m in langgraph fastmcp pydantic yaml rank_bm25 agentevals fastapi; do
  chk "Modul $m importierbar"            "python -c 'import $m'"
done
chk "ruff, bandit, pytest vorhanden"     'command -v ruff && python -m bandit --version && python -m pytest --version'
chk ".env vorhanden und ignoriert"       '[ -f .env ] && git check-ignore -q .env'
if grep -qE "^ANTHROPIC_API_KEY=(sk-ant-EXAMPLE|sk-ant-[A-Za-z0-9_-]{20,})" .env 2>/dev/null; then
  ok "ANTHROPIC_API_KEY gesetzt (.env)"
else
  ko "ANTHROPIC_API_KEY gesetzt (.env) – Zeile: $(grep -E '^ANTHROPIC_API_KEY=' .env 2>/dev/null | cut -c1-24)"
fi
chk ".env enthält nur Secret-Schlüssel"  '[ -z "$(grep -oE "^[A-Za-z_]+" .env | grep -vE "(KEY|SECRET|TOKEN|PASSWORD)$")" ]'
chk "settings.env vorhanden und getrackt" '[ -f settings.env ] && ! git check-ignore -q settings.env'

echo "== Code"
chk "ruff check"                         'ruff check .'
chk "bandit"                             'python -m bandit -q -c pyproject.toml -r src'
chk "pytest (alle, ohne e2e)"            'python -m pytest -q -p no:warnings -x'
N=$(python -m pytest -q -p no:warnings 2>/dev/null | grep -oE "[0-9]+ passed" | tail -1 ); echo "      Tests: ${N:-?}"

echo "== Daten"
chk "Simulator läuft"                    'python -m production_agent.data.simulator | grep -q "Ereignisse"'
chk "Gold ≥ 100 Ereignisse"              'python -c "import sqlite3;c=sqlite3.connect(\"data/gold/mes.sqlite\");assert c.execute(\"select count(*) from downtime_events_gold\").fetchone()[0]>=100"'
chk "nur PackML-Stoppzustände"           'python -c "import sqlite3;c=sqlite3.connect(\"data/gold/mes.sqlite\");s={r[0] for r in c.execute(\"select distinct packml_state from downtime_events_gold\")};assert s<={\"Stopped\",\"Held\",\"Suspended\",\"Aborted\"},s"'
chk "Demo-Ereignis = E-4711, Alarmflut"  'python -c "import sqlite3;c=sqlite3.connect(\"data/gold/mes.sqlite\");r=c.execute(\"select first_alarm_code,alarm_flood from downtime_events_gold order by start_ts desc limit 1\").fetchone();assert r==(\"E-4711\",1),r"'
chk "Replay-Fall auswählbar"             'python -c "import sqlite3;from production_agent.data.replay import select_replay_cases;c=sqlite3.connect(\"data/gold/mes.sqlite\");c.row_factory=sqlite3.Row;cs=select_replay_cases(c,n=1);assert cs and cs[0].truth[\"reason_code\"]"'

echo "== MCP über Protokoll (Replay-Uhr, kein Leck)"
cat > /tmp/_mcpcheck.py <<'PY'
import asyncio, json, os, re, sqlite3
from production_agent.data.replay import select_replay_cases
c=sqlite3.connect("data/gold/mes.sqlite"); c.row_factory=sqlite3.Row
case=select_replay_cases(c,n=1)[0]; os.environ["SIM_NOW"]=case.now
from production_agent.config import get_settings; get_settings.cache_clear()
from fastmcp import Client
from production_agent.mcp.mes_server import mcp
def body(r): return json.loads(re.search(r">\n(.*)\n</tool_data>", r.content[0].text, re.S).group(1))
async def main():
    async with Client(mcp) as cl:
        names={t.name for t in await cl.list_tools()}; assert len(names)==6, names
        al=body(await cl.call_tool("get_active_alarms",{"line_id":"L1","minutes":30})); assert al
        first=al[-1]["alarm_code"]
        hist=body(await cl.call_tool("get_alarm_history",{"alarm_code":first,"limit":50}))
        sim=body(await cl.call_tool("find_similar_incidents",{"alarm_codes":[first],"packml_state":"Held","limit":50}))
        ids={h.get("event_id") for h in hist}|{s.get("event_id") for s in sim}
        assert case.event_id not in ids, "LECK: laufende Störung in Historie"
        imp=body(await cl.call_tool("estimate_impact",{"line_id":"L1","expected_downtime_min":20})); assert imp["cost_eur"]>0
        print(f"      Fall {case.event_id} @ {case.now}: {len(al)} Alarme, {len(hist)} Historie, {len(sim)} ähnliche, Impact {imp['cost_eur']} €")
asyncio.run(main())
PY
chk "6 Werkzeuge, kein Leck, Impact > 0" 'python /tmp/_mcpcheck.py'
python /tmp/_mcpcheck.py 2>/dev/null | tail -1

echo "== Graph"
chk "interrupt am Freigabeknoten + resume" 'python -c "
from langgraph.types import Command
from production_agent.graph.workflow import build_graph
g=build_graph();cfg={\"configurable\":{\"thread_id\":\"selftest\"}}
r=g.invoke({\"line_id\":\"L1\",\"alarms\":[{}]*12,\"actions\":[{\"title\":\"Not-Aus überbrücken\",\"description\":\"\",\"confidence\":.99},{\"title\":\"Prüfe Sensor\",\"description\":\"\",\"confidence\":.9}],\"trace\":[]},cfg)
acts=[a[\"title\"] for a in r[\"__interrupt__\"][0].value[\"actions\"]];assert acts==[\"Prüfe Sensor\"],acts
f=g.invoke(Command(resume={\"approved\":True}),cfg);assert f[\"approval\"][\"approved\"]"'
chk "API /health"                        'SIM_NOW="" python -c "
from fastapi.testclient import TestClient
from production_agent.api.server import app
assert TestClient(app).get(\"/health\").json()[\"ok\"]"'

echo "== Guardian, Hooks, Repo-Hygiene"
chk "Guardian ok auf aktuellem Index"    'git add -A && python autopilot/guardian.py'
chk "pre-commit + commit-msg Hooks"      'test -x .git/hooks/pre-commit && test -x .git/hooks/commit-msg'
chk "commit-msg lehnt schlechte Message ab" 'printf "update stuff\n" > /tmp/_m && ! python autopilot/commit_check.py /tmp/_m'
chk "commit-msg akzeptiert Konvention"   'printf "feat(WP1): x\n\nGebaut: -\n\nGate: grün | Review: pass | Guardian: ok\n" > /tmp/_m && python autopilot/commit_check.py /tmp/_m'
chk "keine verbotenen Dateien getrackt"  '! git ls-files | grep -Ei "egg-info|(^|/)\.env$|\.sqlite|\.venv|__pycache__|audit\.jsonl"'
chk "kein API-Key im Index"              '! git grep -qE "sk-ant-[A-Za-z0-9_-]{20,}" -- . ":!.env.example"'

chk "decisions.yaml eingefroren"         'test -s .guardian/decisions.sha256'
chk "Autopilot dry-run ohne {{ }}"       '[ "$(python autopilot/run.py --dry-run | grep -c "{{")" = "0" ]'
chk "status.json aktuell"                'python autopilot/status.py --check'
chk "Coverage ≥ 80 %"                    'python -c "import json;assert json.load(open(\"coverage.json\"))[\"totals\"][\"percent_covered\"]>=80"'

echo "== Leck-Simulation (Guardian S7/S8, wird sofort zurückgenommen)"
cp .env /tmp/_env; echo "SELFTEST_TOKEN=selftest-0123456789abcdef" >> /tmp/_env  # gitleaks:allow
echo "leak selftest-0123456789abcdef" > docs/_leak.md  # gitleaks:allow
python -c "print('Firma '+bytes.fromhex('44656c6f69747465').decode())" > docs/_pub.md
git add docs/_leak.md docs/_pub.md
OUT=$(GUARDIAN_ENV_FILE=/tmp/_env python autopilot/guardian.py 2>&1)
git rm -q --cached docs/_leak.md docs/_pub.md; rm -f docs/_leak.md docs/_pub.md /tmp/_env
echo "$OUT" | grep -q "S7 Wert aus .env" && ok "S7 erkennt kopierten .env-Wert" || ko "S7 erkennt kopierten .env-Wert"
echo "$OUT" | grep -q "S8 Begriff"       && ok "S8 erkennt Blocklisten-Begriff" || ko "S8 erkennt Blocklisten-Begriff"
git add -A >/dev/null 2>&1

echo; echo "== Ergebnis: $P PASS, $F FAIL"; [ "$F" -eq 0 ]
