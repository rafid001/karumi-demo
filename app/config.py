from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

LLMProvider = Literal["groq", "gemini", "claude"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql://user:password@localhost:5432/demo_agent"
    llm_provider: LLMProvider = "groq"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    groq_vision_model: str = "meta-llama/llama-4-scout-17b-16e-instruct"
    google_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-20250514"
    screenshot_dir: str = "./screenshots"
    drift_check_interval_hours: int = 6
    drift_visual_threshold: float = 0.05
    auto_heal_on_drift: bool = True
    playwright_headless: bool = True
    crawl_max_pages: int = 50
    crawl_max_depth: int = 5


settings = Settings()
