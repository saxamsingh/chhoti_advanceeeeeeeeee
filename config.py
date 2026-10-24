"""Settings, read from environment variables and an optional .env file (repo root or backend/).

Every variable in .env.example is a field here. Nothing in the code reads os.environ directly.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(ROOT_DIR / ".env", BACKEND_DIR / ".env"),
        extra="ignore",
        case_sensitive=False,
    )

    # TinyFish
    tinyfish_mode: Literal["live", "replay"] = "replay"
    tinyfish_api_key: str = ""
    tinyfish_record: bool = False
    tinyfish_budget_agent_runs: int = 10
    tinyfish_budget_free_calls: int = 200
    tinyfish_max_concurrent_runs: int = 2
    tinyfish_webhook_token: str = ""
    tinyfish_cache_ttl_seconds: int = 3600

    # Database
    db_backend: Literal["sqlite", "supabase"] = "sqlite"
    sqlite_path: Path = BACKEND_DIR / "khetkaaj.db"
    supabase_url: str = ""
    supabase_key: str = ""

    # Demo area and safety gate
    demo_state: str = "Uttar Pradesh"
    demo_district: str = "Meerut"
    confidence_threshold: float = 0.85

    # Channels
    public_base_url: str = ""
    cors_origins: str = "http://localhost:5173"
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = ""
    bhashini_user_id: str = ""
    bhashini_api_key: str = ""
    llm_phrasing: bool = False
    anthropic_api_key: str = ""
    llm_model: str = "claude-haiku-5-5"

    # Paths (not environment variables; overridden in tests)
    fixtures_dir: Path = BACKEND_DIR / "fixtures"
    knowledge_dir: Path = ROOT_DIR / "knowledge"
    files_dir: Path = BACKEND_DIR / "files"
    cache_dir: Path = BACKEND_DIR / ".cache" / "tinyfish"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def tinyfish_fixtures_dir(self) -> Path:
        return self.fixtures_dir / "tinyfish"


@lru_cache
def get_settings() -> Settings:
    return Settings()
