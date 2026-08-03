"""EarthPulse AI — centralized settings. All env-driven, safe defaults for keyless dev."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "EarthPulse AI"
    api_prefix: str = "/api/v1"

    # sqlite for zero-config dev; postgresql+psycopg://... for prod
    database_url: str = "sqlite:///./earthpulse.db"
    echo_sql: bool = False

    # LLM — keyless mode is the default; set OPENAI_API_KEY to go live.
    llm_mode: str = "auto"  # auto | templates
    openai_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"

    seed_on_boot: bool = True
    ws_enabled: bool = True  # set false in tests to avoid background broadcaster races
    # Operational scope: "chennai" (pilot, 15 zones) or "tamilnadu" (state-wide, ~53 zones)
    scope: str = "chennai"
    tick_seconds: float = 3.0
    simulated: bool = True  # synthetic data flag surfaced in provenance

    # Real-data ingestion (optional live hooks; left empty the adapters run in honest demo mode)
    imd_endpoint: str = ""
    imd_token: str = ""
    gpm_endpoint: str = ""
    gpm_token: str = ""
    reservoir_endpoint: str = ""
    reservoir_token: str = ""

    cors_origins: str = "http://localhost:3000"

    @property
    def llm_enabled(self) -> bool:
        return self.llm_mode == "auto" and bool(self.openai_api_key)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
