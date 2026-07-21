"""Reasoning Worker — DeepSeek prompt refinement.

Reads from the reasoning queue, calls DeepSeek API to refine the raw prompt
into an optimized coloring page prompt, writes the result to the image queue.
"""

import json
import os
import logging
from typing import Optional

from src.core.message import Message
from src.core.coloring_domain import AgeGroup, Style
from src.core.prompt_rules import build_system_prompt, build_refined_prompt, build_negative_prompt
from src.workers.base import Worker, TransientError, FatalError


logger = logging.getLogger(__name__)


class ReasoningWorker(Worker):
    """Transforms raw user prompts into optimized coloring page prompts via DeepSeek.

    If DeepSeek API is unavailable, falls back to template-based prompt construction.
    """

    def __init__(
        self,
        input_queue: str = "reasoning",
        output_queue: str = "image",
        queue_dir: str = ".queues/coloring",
        api_key: str | None = None,
        api_base: str = "https://api.deepseek.com/v1",
        model: str = "deepseek-chat",
        use_api: bool = True,
    ):
        super().__init__(input_queue, output_queue, queue_dir)
        self.api_key = api_key or os.environ.get("FACTORY_DEEPSEEK_API_KEY", "")
        self.api_base = api_base
        self.model = model
        self.use_api = use_api and bool(self.api_key)

    @property
    def worker_name(self) -> str:
        return "reasoning"

    def process(self, message: Message) -> Optional[Message]:
        """Refine a raw prompt using DeepSeek or template fallback."""
        payload = message.payload
        raw_prompt = payload.get("raw_prompt", "")
        age_group_str = payload.get("age_group", "child")
        style_str = payload.get("style", "simple")

        try:
            age_group = AgeGroup(age_group_str)
            style = Style(style_str)
        except ValueError as e:
            raise FatalError(f"Invalid age_group or style: {e}") from e

        if self.use_api:
            try:
                result = self._call_deepseek(raw_prompt, age_group, style)
            except TransientError:
                raise
            except Exception as e:
                logger.warning("[reasoning] DeepSeek API failed, using fallback: %s", e)
                result = self._template_fallback(raw_prompt, age_group, style)
        else:
            logger.info("[reasoning] No API key, using template fallback")
            result = self._template_fallback(raw_prompt, age_group, style)

        image_payload = {
            "request_id": message.trace_id,
            "refined_prompt": result["refined_prompt"],
            "negative_prompt": result["negative_prompt"],
            "style": style.value,
        }

        return message.with_payload(image_payload, new_type="image_task")

    def _call_deepseek(self, prompt: str, age_group: AgeGroup, style: Style) -> dict:
        """Call DeepSeek chat completion API."""
        import httpx

        system_prompt = build_system_prompt()
        user_prompt = json.dumps({
            "raw_prompt": prompt,
            "age_group": age_group.value,
            "style": style.value,
        })

        try:
            response = httpx.post(
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.7,
                    "max_tokens": 1024,
                },
                timeout=60.0,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]

            # Parse JSON from response
            result = json.loads(content)
            return {
                "refined_prompt": result.get("refined_prompt", build_refined_prompt(prompt, age_group, style)),
                "negative_prompt": result.get("negative_prompt", build_negative_prompt(style)),
            }
        except httpx.TimeoutException:
            raise TransientError("DeepSeek API timeout")
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (429, 502, 503):
                raise TransientError(f"DeepSeek API {e.response.status_code}")
            raise FatalError(f"DeepSeek API error: {e.response.status_code}")
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("[reasoning] Failed to parse DeepSeek response: %s", e)
            return self._template_fallback(prompt, age_group, style)

    def _template_fallback(self, prompt: str, age_group: AgeGroup, style: Style) -> dict:
        """Build prompt using templates when API is unavailable."""
        return {
            "refined_prompt": build_refined_prompt(prompt, age_group, style),
            "negative_prompt": build_negative_prompt(style),
        }
