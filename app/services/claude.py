import base64
import json
from pathlib import Path

import anthropic

from app.config import settings
from app.services.llm_utils import extract_json, fallback_page_analysis


class ClaudeService:
    def __init__(self, api_key: str | None = None):
        key = api_key or settings.anthropic_api_key
        self.client = anthropic.Anthropic(api_key=key) if key else None

    def analyze_page(self, url: str, elements: list[dict], screenshot_path: str | None = None) -> dict:
        prompt = f"""You are analyzing a screenshot of a SaaS product page.

Page URL: {url}
HTML elements found: {json.dumps(elements[:50], indent=2)}

Answer the following:
1. What is this page called?
2. What is its primary purpose?
3. What is the most important action a user takes here?
4. What page does the primary action lead to?
5. Is this a key moment in the user journey? (onboarding, aha moment, core feature)

Respond in JSON with keys: page_name, purpose, primary_action, leads_to, journey_moment, is_key_moment."""

        if not self.client:
            return fallback_page_analysis(url, elements)

        content: list[dict] = []
        if screenshot_path and Path(screenshot_path).exists():
            image_data = base64.standard_b64encode(Path(screenshot_path).read_bytes()).decode()
            content.append(
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/png", "data": image_data},
                }
            )
        content.append({"type": "text", "text": prompt})

        response = self.client.messages.create(
            model=settings.claude_model,
            max_tokens=1024,
            messages=[{"role": "user", "content": content}],
        )
        return extract_json(response.content[0].text)

    def compare_screenshots(self, old_path: str, new_path: str, visual_diff_score: float) -> dict:
        prompt = f"""You are comparing two screenshots of the same page in a SaaS product.

The visual diff score is {visual_diff_score} (0 = identical, 1 = completely different).

Answer the following:
1. What changed between these two screenshots?
2. Is this a meaningful functional change or a cosmetic change?
3. If meaningful: which user flows might be affected?
4. Severity: low / medium / high

Respond in JSON with keys: changes, change_type, affected_flows, severity."""

        content: list[dict] = []
        for path in (old_path, new_path):
            image_data = base64.standard_b64encode(Path(path).read_bytes()).decode()
            content.append(
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/png", "data": image_data},
                }
            )
        content.append({"type": "text", "text": prompt})

        response = self.client.messages.create(
            model=settings.claude_model,
            max_tokens=1024,
            messages=[{"role": "user", "content": content}],
        )
        return extract_json(response.content[0].text)

    def generate_demo_path(self, graph: dict, persona: str) -> list[dict]:
        prompt = f"""You are a world-class SaaS sales engineer.

You have access to the following knowledge graph of a product:
{json.dumps(graph, indent=2)}

Your prospect is: {persona}

Generate the ideal demo path for this prospect. Focus on reaching the "aha moment" as fast as possible.

Return an ordered list of steps. Each step:
- node_id: the graph node to navigate to
- action: what to do on this page
- narration: what to say to the prospect at this moment (natural, conversational, not salesy)

Respond in JSON with key "steps" containing the ordered list."""

        response = self.client.messages.create(
            model=settings.claude_model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        result = extract_json(response.content[0].text)
        return result.get("steps", result if isinstance(result, list) else [])

    def reconcile_subgraph(self, old_subgraph: dict, new_subgraph: dict) -> dict:
        prompt = f"""You are reconciling an updated UI subgraph with existing product knowledge.

Old subgraph:
{json.dumps(old_subgraph, indent=2)}

New observations:
{json.dumps(new_subgraph, indent=2)}

Merge these into a coherent updated subgraph. Identify what changed, what was removed, and what was added.

Respond in JSON with keys: merged_nodes, merged_edges, change_summary."""

        response = self.client.messages.create(
            model=settings.claude_model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        return extract_json(response.content[0].text)

    def check_health(self) -> dict:
        if not self.client:
            return {"status": "error", "detail": "ANTHROPIC_API_KEY not set"}
        try:
            self.client.messages.create(
                model=settings.claude_model,
                max_tokens=16,
                messages=[{"role": "user", "content": "Reply with exactly: OK"}],
            )
            return {"status": "ok"}
        except Exception as exc:
            return {"status": "error", "detail": str(exc)[:300]}

    def check_health(self) -> dict:
        if not self.client:
            return {"status": "error", "detail": "ANTHROPIC_API_KEY not set"}
        try:
            self.client.messages.create(
                model=settings.claude_model,
                max_tokens=16,
                messages=[{"role": "user", "content": "Reply with exactly: OK"}],
            )
            return {"status": "ok"}
        except Exception as exc:
            return {"status": "error", "detail": str(exc)[:300]}
