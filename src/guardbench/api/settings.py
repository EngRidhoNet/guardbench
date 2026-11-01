from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GUARDBENCH_", env_file=".env")

    database_url: str = "sqlite:///./guardbench.db"
    api_key: str | None = None
    cors_origins: str = "http://localhost:5173,http://localhost:3000"


settings = Settings()
