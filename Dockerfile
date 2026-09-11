FROM python:3.11-slim
RUN useradd --create-home --uid 10001 agent
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir -e .
USER agent
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "production_agent.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
