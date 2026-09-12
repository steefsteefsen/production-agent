.PHONY: install lint test security run-mes run-rag run-api
install: ; pip install -e ".[dev]" && pre-commit install && pre-commit install --hook-type commit-msg && python autopilot/guardian.py --init || true
guardian: ; python autopilot/guardian.py
lint: ; ruff check . && ruff format --check .
test: ; mkdir -p .guardian && pytest --cov=production_agent --cov-report=term-missing:skip-covered --cov-report=json:.guardian/coverage.json --cov-fail-under=80
security: ; bandit -c pyproject.toml -r src && pip-audit || true
run-mes: ; python -m production_agent.mcp.mes_server
run-rag: ; python -m production_agent.mcp.rag_server
run-api: ; uvicorn production_agent.api.server:app --reload
