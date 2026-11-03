from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "local"
    app_version: str = "0.1.0"

    llm_provider: str = "deepseek"
    llm_model: str = "deepseek-chat"
    llm_temperature: float = 0.2

    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    deepseek_api_key: str | None = None

    database_path: Path = Path("/data/loja.db")
    runtime_path: Path = Path("/data/runtime.db")
    data_dir: Path = Path("/app/data")
    logs_dir: Path = Path("/app/logs")

    session_ttl_minutes: int = 30
    budget_tokens: int = 60_000
    max_messages_per_minute: int = 10
    # 60/hora: o eval abre 14 sessoes por execucao e uma pessoa clicando "nova sessao"
    # durante uma demo nao pode ser bloqueada. Ainda e um freio de denial-of-wallet.
    max_sessions_per_hour: int = 60
    audit_enabled: bool = True

    # origens liberadas para a interface (lista separada por virgula). Vazio desliga o CORS.
    # 5173 = serve.py de desenvolvimento · 8080 = container nginx do compose
    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:8080,http://127.0.0.1:8080,"
        "http://localhost:3000,http://localhost:4173"
    )

    @property
    def policies_dir(self) -> Path:
        return self.data_dir / "policies"

    @property
    def allowed_origins(self) -> list[str]:
        """Origem liberada para a interface. Lista vazia desliga o CORS."""
        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]

    @property
    def provider_api_key(self) -> str | None:
        raw = {
            "openai": self.openai_api_key,
            "anthropic": self.anthropic_api_key,
            "deepseek": self.deepseek_api_key,
        }.get(self.llm_provider)
        return raw.strip() if raw and raw.strip() else None


@lru_cache
def get_settings() -> Settings:
    return Settings()
