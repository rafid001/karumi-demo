import json
import re


def extract_json(text: str) -> dict:
    text = text.strip()
    fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1)
    return json.loads(text)


def fallback_page_analysis(url: str, elements: list[dict]) -> dict:
    title = url.rstrip("/").split("/")[-1] or "Home"
    return {
        "page_name": title.replace("-", " ").title(),
        "purpose": f"Page at {url}",
        "primary_action": elements[0]["text"] if elements else "Navigate",
        "leads_to": "Unknown",
        "journey_moment": "unknown",
        "is_key_moment": False,
    }
