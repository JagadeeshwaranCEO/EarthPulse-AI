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

    # Mutating-endpoint guard: empty api_key = keyless dev mode (guard off).
    # Set EARTHPULSE_API_KEY to enforce X-API-Key on the POST routes.
    api_key: str = ""
    mutation_rate_per_minute: int = 30

    # ---- Offline SMS alerting (see app/notification/) ----
    sms_enabled: bool = False
    # Comma-separated failover chain, first usable wins: log,twilio,aws_sns,...
    sms_providers: str = "log"
    sms_sender_id: str = "EARTHPLS"
    sms_risk_threshold: float = 0.85  # alert fires when risk_probability >= this
    sms_min_level: str = "warning"  # advisory | watch | warning | critical
    sms_resend_delta: float = 0.10  # re-alert only when probability shifts by this much
    sms_retry_count: int = 3
    sms_retry_base_seconds: float = 2.0
    sms_retry_max_seconds: float = 30.0
    sms_provider_timeout_s: float = 10.0
    sms_quiet_hours: str = ""  # e.g. "22:00-06:00" (UTC)
    sms_template: str = ""
    sms_otp_ttl_s: int = 600
    sms_otp_secret: str = ""  # salt for OTP hashing; set a long random value in prod

    # Provider credentials (never log these)
    sms_twilio_account_sid: str = ""
    sms_twilio_auth_token: str = ""
    sms_twilio_from: str = ""
    sms_messagebird_api_key: str = ""
    sms_messagebird_originator: str = ""
    sms_vonage_api_key: str = ""
    sms_vonage_api_secret: str = ""
    sms_vonage_from: str = ""
    sms_textlocal_api_key: str = ""
    sms_textlocal_sender: str = ""
    sms_msg91_auth_key: str = ""
    sms_msg91_sender: str = ""
    sms_aws_access_key: str = ""
    sms_aws_secret_key: str = ""
    sms_aws_session_token: str = ""
    sms_aws_region: str = "ap-south-1"

    @property
    def llm_enabled(self) -> bool:
        return self.llm_mode == "auto" and bool(self.openai_api_key)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # ---- NextGen: field intel + scenario simulator + ghost mode + push ----
    field_auto_confirm_agreement: float = 0.80  # report auto-confirmed when agreement >= this
    field_geo_radius_km: float = 25.0  # max distance a report binds to a zone

    scenario_max_steps: int = 72  # hard ceiling on duration_h/step_h frames
    scenario_impact_population_pct: float = 0.12  # shelter ledger share of exposed pop

    ghost_enabled: bool = False  # autonomous escalation agent (watchdog thread)
    ghost_check_seconds: float = 20.0
    ghost_broadcast_min_level: str = "warning"  # advisory|watch|warning|critical
    ghost_broadcast_max_per_cycle: int = 25

    push_enabled: bool = True
    push_contact: str = "ops@earthpulse.ai"
    push_ttl_seconds: int = 3600
    vapid_private_pem: str = ""  # optional; generated + persisted in DB if empty
    vapid_public_pem: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
