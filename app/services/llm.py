from typing import Literal, Protocol

from app.config import settings
from app.services.claude import ClaudeService
from app.services.gemini import GeminiService
from app.services.groq import GroqService

LLMProvider = Literal["groq", "gemini", "claude"]


class LLMService(Protocol):
    def analyze_page(self, url: str, elements: list[dict], screenshot_path: str | None = None) -> dict: ...

    def compare_screenshots(self, old_path: str, new_path: str, visual_diff_score: float) -> dict: ...

    def generate_demo_path(self, graph: dict, persona: str) -> list[dict]: ...

    def reconcile_subgraph(self, old_subgraph: dict, new_subgraph: dict) -> dict: ...


def get_llm_service(provider: LLMProvider | None = None) -> LLMService:
    selected = provider or settings.llm_provider
    if selected == "claude":
        return ClaudeService()
    if selected == "gemini":
        return GeminiService()
    return GroqService()


def get_llm_model(provider: LLMProvider | None = None) -> str:
    selected = provider or settings.llm_provider
    if selected == "claude":
        return settings.claude_model
    if selected == "gemini":
        return settings.gemini_model
    return f"{settings.groq_model} (vision: {settings.groq_vision_model})"


def check_llm_health(provider: LLMProvider | None = None) -> dict:
    service = get_llm_service(provider)
    result = service.check_health()  # type: ignore[attr-defined]
    return {
        "provider": provider or settings.llm_provider,
        "service": type(service).__name__,
        "model": get_llm_model(provider),
        **result,
    }
