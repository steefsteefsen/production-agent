.PHONY: install install-demo ingest lint test security run-mes run-rag run-api ui e2e e2e-mock e2e-live ops
install: ; pip install -e ".[dev]" && pre-commit install && pre-commit install --hook-type commit-msg && python autopilot/guardian.py --init || true
# Demo-Installation: embeddings sind hier PFLICHT (Vektor-Suche muss verfügbar sein). CPU-Torch statt
# CUDA (kleines Modell intfloat/multilingual-e5-small, CPU genügt; schlank für CI). Danach `make
# ingest` einmalig ausführen, um Modell zu cachen und den Qdrant-Index zu bauen (kein Live-Download
# im Interview).
install-demo: ; pip install torch --index-url https://download.pytorch.org/whl/cpu && pip install -e ".[dev,e2e,embeddings]" && $(MAKE) ingest
ingest: ; python -m production_agent.mcp.rag_server --ingest
guardian: ; python autopilot/guardian.py
lint: ; ruff check . && ruff format --check .
test: ; mkdir -p .guardian && pytest --cov=production_agent --cov-report=term-missing:skip-covered --cov-report=json:.guardian/coverage.json --cov-fail-under=80
security: ; bandit -c pyproject.toml -r src && pip-audit || true
run-mes: ; python -m production_agent.mcp.mes_server
run-rag: ; python -m production_agent.mcp.rag_server
run-api: ; uvicorn production_agent.api.server:app --reload
ui: ; cd frontend && npm run dev
e2e: ; pytest -q -m e2e tests/e2e
e2e-mock: ; python scripts/e2e_replay.py
e2e-live: ; LLM_MODE=live python scripts/e2e_replay.py
ops: ; uvicorn autopilot.ops.app:app --host 127.0.0.1 --port 8010 --reload
