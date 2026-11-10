from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../.env",   # the repo-root .env, one level up from backend/
        extra="ignore",
    )

    postgres_user: str
    postgres_password: str
    postgres_db: str
    app_rw_password: str
    analyst_ro_password: str

    db_host: str = "localhost"
    db_port: int = 5432
    max_upload_mb: int = 50

    # AI agent. Put ANTHROPIC_API_KEY in the repo-root .env.
    anthropic_api_key: str | None = None
    agent_model: str = "claude-opus-5-5"

    @property
    def app_rw_url(self) -> str:
        return (
            f"postgresql+psycopg://app_rw:{self.app_rw_password}"
            f"@{self.db_host}:{self.db_port}/{self.postgres_db}"
        )

    @property
    def analyst_ro_url(self) -> str:
        return (
            f"postgresql+psycopg://analyst_ro:{self.analyst_ro_password}"
            f"@{self.db_host}:{self.db_port}/{self.postgres_db}"
        )


settings = Settings()
