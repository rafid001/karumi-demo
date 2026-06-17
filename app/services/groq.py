import base64
import json
from pathlib import Path

from groq import Groq

from app.config import settings
from app.services.llm_utils import extract_json, fallback_page_analysis


class GroqService:
    def __init__(self, api_key: str | None = None):
        key = api_key or settings.groq_api_key
        self.client = Groq(api_key=key) if key else None

    def _image_part(self, path: str) -> dict:
        data = base64.standard_b64encode(Path(path).read_bytes()).decode()
        return {
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{data}"},
        }

    def _generate(
        self,
        prompt: str,
        image_paths: list[str] | None = None,
        max_tokens: int = 4096,
        model: str | None = None,
    ) -> str:
        if not self.client:
            raise RuntimeError("GROQ_API_KEY not configured")

        content: list = []
        for path in image_paths or []:
            if Path(path).exists():
                content.append(self._image_part(path))
        content.append({"type": "text", "text": prompt})

        response = self.client.chat.completions.create(
            model=model or settings.groq_model,
            messages=[{"role": "user", "content": content}],
            max_completion_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content or ""

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

        images = [screenshot_path] if screenshot_path else None
        return extract_json(
            self._generate(
                prompt,
                image_paths=images,
                max_tokens=1024,
                model=settings.groq_vision_model,
            )
        )

    def compare_screenshots(self, old_path: str, new_path: str, visual_diff_score: float) -> dict:
        prompt = f"""You are comparing two screenshots of the same page in a SaaS product.

The visual diff score is {visual_diff_score} (0 = identical, 1 = completely different).

The first image is the old screenshot. The second image is the new screenshot.

Answer the following:
1. What changed between these two screenshots?
2. Is this a meaningful functional change or a cosmetic change?
3. If meaningful: which user flows might be affected?
4. Severity: low / medium / high

Respond in JSON with keys: changes, change_type, affected_flows, severity."""

        return extract_json(
            self._generate(
                prompt,
                image_paths=[old_path, new_path],
                max_tokens=1024,
                model=settings.groq_vision_model,
            )
        )

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

        result = extract_json(self._generate(prompt, max_tokens=4096))
        return result.get("steps", result if isinstance(result, list) else [])

    def reconcile_subgraph(self, old_subgraph: dict, new_subgraph: dict) -> dict:
        prompt = f"""You are reconciling an updated UI subgraph with existing product knowledge.

Old subgraph:
{json.dumps(old_subgraph, indent=2)}

New observations:
{json.dumps(new_subgraph, indent=2)}

Merge these into a coherent updated subgraph. Identify what changed, what was removed, and what was added.

Respond in JSON with keys: merged_nodes, merged_edges, change_summary."""

        return extract_json(self._generate(prompt, max_tokens=4096))

    def check_health(self) -> dict:
        if not self.client:
            return {"status": "error", "detail": "GROQ_API_KEY not set"}
        try:
            self.client.chat.completions.create(
                model=settings.groq_model,
                messages=[{"role": "user", "content": "Reply in JSON with key message set to OK"}],
                max_completion_tokens=16,
                response_format={"type": "json_object"},
            )
            return {"status": "ok"}
        except Exception as exc:
            return {"status": "error", "detail": str(exc)[:300]}
