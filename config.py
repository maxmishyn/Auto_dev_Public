#
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # ——— OpenAI ———
    openai_api_key: str
    openai_base_url: str = "https://api.openai.com"
    vision_model: str = "o4-mini"
    translate_model: str = "gpt-4.1-mini"
    # ——— Limits ———
    active_batch_limit: int = 10
    per_key_batch_limit: int = 2
    line_size_limit: int = 1_048_576
    file_size_limit: int = 200 * 1024 * 1024
    max_lines_per_batch: int = 50_000
    # ——— Security ———
    shared_key: str
    # ——— Redis ———
    redis_url: str = "redis://localhost:6379/0"
    # ——— Retries ———
    max_retries: int = 5
    base_delay: float = 2.0   # seconds
    # ——— Timeouts ———
    connect_timeout: float = 3.0
    read_timeout: float = 5.0

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()