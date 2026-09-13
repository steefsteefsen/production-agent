"""Zentrale Konfiguration. Geheimnisse ausschließlich über .env / Umgebungsvariablen."""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Modell-IDs zentral und über Umgebungsvariablen überschreibbar (LLM_MODEL_MAIN / LLM_MODEL_JUDGE).
# Default = Sonnet 5 für die Begründungsknoten 4 (Ursache) und 6 (Maßnahmen): Kostenentscheidung,
# Opus bleibt für die Demo zu teuer, Sonnet trägt die Begründungsqualität (ADR-0008, docs/e2e.md).
# Der Judge/Klassifikation bleibt Haiku 4.5.
DEFAULT_MODEL_MAIN = "claude-sonnet-5"
DEFAULT_MODEL_JUDGE = "claude-haiku-4-5-20251001"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("settings.env", ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    anthropic_api_key: SecretStr = SecretStr("")
    # Knoten 4 (Ursache) und 6 (Maßnahmen). ENV: LLM_MODEL_MAIN
    llm_model_main: str = DEFAULT_MODEL_MAIN
    # LLM-as-Judge und Klassifikation. ENV: LLM_MODEL_JUDGE
    llm_model_judge: str = DEFAULT_MODEL_JUDGE
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
