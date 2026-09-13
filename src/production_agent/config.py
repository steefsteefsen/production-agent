"""Zentrale Konfiguration. Geheimnisse ausschließlich über .env / Umgebungsvariablen."""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("settings.env", ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    anthropic_api_key: SecretStr = SecretStr("")
    anthropic_model: str = "claude-opus-5"
    anthropic_model_fast: str = "claude-haiku-4-5-20251001"
    # LLM-Schalter für Knoten 4/6: "mock" = deterministisches Mock-LLM ohne API-Schlüssel
    # (E2E/CI), "live" = ChatAnthropic. build_graph(llm=...) sticht diesen Schalter.
    llm_mode: str = "mock"

    mes_db_path: str = "data/gold/mes.sqlite"
    checkpoint_db_path: str = "data/checkpoints.sqlite"
    audit_log_path: str = "data/audit.jsonl"

    # Replay-Uhr: leer = echte Zeit. Gesetzt = der Agent "lebt" zu diesem Zeitpunkt (ISO-8601).
    sim_now: str = ""

    max_rows_per_tool: int = 200
    max_tool_result_chars: int = 8000
    confidence_threshold_recommend: float = 0.70

    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://localhost:3000"

    @property
    def langfuse_enabled(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
