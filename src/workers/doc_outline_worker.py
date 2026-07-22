"""Doc Outline Worker — generates document outlines from topics.

Reads from the doc.outline queue, calls DeepSeek to produce a structured
document outline (sections, key points, prerequisites), and writes the
result to the doc.write queue for the DocWriterWorker.
"""
from __future__ import annotations

import json
import os
import time
import logging
from typing import Optional

from src.core.message import Message
from src.workers.base import Worker, TransientError, FatalError


logger = logging.getLogger(__name__)

OUTLINE_SYSTEM_PROMPT = """You are a documentation architect and technical writer.
Given a documentation topic, produce a structured document outline.

You MUST respond with valid JSON only, using this exact schema:
{
  "title": "Document Title",
  "sections": [
    {
      "heading": "Section Heading",
      "description": "What this section covers",
      "key_points": ["Key point 1", "Key point 2"],
      "code_examples": false
    }
  ],
  "target_audience": "Description of who this is for",
  "prerequisites": ["Prerequisite 1", "Prerequisite 2"]
}

Guidelines:
- Title should be clear and descriptive.
- Sections in logical order: introduction → setup → core content → advanced → conclusion.
- Each section description should be 1-2 sentences.
- Key points are the essential takeaways for that section.
- Code examples flag should be true for implementation-heavy sections.
- Keep sections focused — each should teach one cohesive concept.
"""


class DocOutlineWorker(Worker):
    """Generates structured document outlines via DeepSeek."""

    def __init__(
        self,
        input_queue: str = "doc.outline",
        output_queue: str = "doc.write",
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
        return "doc_outline"

    def process(self, message: Message) -> Optional[Message]:
        payload = message.payload
        topic = payload.get("topic", "")
        doc_type = payload.get("document_type", "guide")
        tone = payload.get("tone", "formal")
        max_sections = payload.get("max_sections", 6)
        audience = payload.get("audience", "")

        if not topic or len(topic) < 5:
            raise FatalError(f"Topic too short ({len(topic)} chars, min 5)")

        if self.use_api:
            try:
                result = self._call_deepseek(topic, doc_type, tone, max_sections, audience)
            except TransientError:
                raise
            except Exception as e:
                logger.warning("[doc_outline] API failed, using fallback: %s", e)
                result = self._template_fallback(topic, doc_type, max_sections)
        else:
            logger.info("[doc_outline] No API key, using template fallback")
            result = self._template_fallback(topic, doc_type, max_sections)

        outline_payload = {
            "request_id": message.trace_id,
            "topic": topic,
            "title": result.get("title", topic),
            "document_type": doc_type,
            "format": payload.get("format", "markdown"),
            "tone": tone,
            "sections": result.get("sections", []),
            "target_audience": result.get("target_audience", audience),
            "prerequisites": result.get("prerequisites", []),
            "metadata": {
                "model": self.model if self.use_api else "template",
                "outline_time_ms": result.get("_generation_time_ms", 0),
            },
        }

        return message.with_payload(outline_payload, new_type="doc_outline")

    def _call_deepseek(self, topic, doc_type, tone, max_sections, audience):
        import httpx

        user_prompt = json.dumps({
            "topic": topic,
            "document_type": doc_type,
            "tone": tone,
            "max_sections": max_sections,
            "target_audience": audience or "general readers",
        })

        start = time.monotonic()
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
                        {"role": "system", "content": OUTLINE_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.6,
                    "max_tokens": 2048,
                },
                timeout=60.0,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            result = json.loads(content)
            result["_generation_time_ms"] = int((time.monotonic() - start) * 1000)
            return result
        except httpx.TimeoutException:
            raise TransientError("DeepSeek API timeout")
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (429, 502, 503):
                raise TransientError(f"DeepSeek API {e.response.status_code}")
            raise FatalError(f"DeepSeek API error: {e.response.status_code}")
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("[doc_outline] Failed to parse response: %s", e)
            return self._template_fallback(topic, doc_type, max_sections)

    def _template_fallback(self, topic, doc_type, max_sections):
        import hashlib
        # Deterministic section generation based on topic hash
        seed = int(hashlib.md5(topic.encode()).hexdigest()[:8], 16)
        templates = [
            ("Introduction", f"Overview of {topic} and scope of this document"),
            ("Background", f"Context and foundational concepts for {topic}"),
            ("Core Concepts", f"The main principles and architecture of {topic}"),
            ("Implementation", f"Step-by-step guidance on working with {topic}"),
            ("Best Practices", f"Recommended approaches and common pitfalls for {topic}"),
            ("Examples", f"Practical examples demonstrating {topic}"),
            ("Troubleshooting", f"Common issues and solutions when using {topic}"),
            ("Conclusion", f"Summary of key takeaways and next steps for {topic}"),
        ]
        count = min(max_sections, len(templates))
        # Pick sections based on topic hash
        idx = seed % (len(templates) - count + 1)
        sections = [
            {
                "heading": templates[i][0],
                "description": templates[i][1],
                "key_points": [f"Key aspect of {templates[i][0].lower()}"],
                "code_examples": templates[i][0] in ("Implementation", "Examples"),
            }
            for i in range(idx, idx + count)
        ]
        return {
            "title": f"{doc_type.replace('_', ' ').title()}: {topic}",
            "sections": sections,
            "target_audience": "General readers interested in this topic",
            "prerequisites": ["Basic understanding of the subject area"],
            "_generation_time_ms": 0,
        }


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    worker = DocOutlineWorker(use_api=bool(os.environ.get("FACTORY_DEEPSEEK_API_KEY")))
    worker.start()
