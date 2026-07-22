"""Research Worker — DeepSeek-powered deep research.

Reads from the research.tasks queue, calls DeepSeek to produce structured
findings, and writes the result to the research.synthesis queue.

Supports three research depths:
- quick: single-pass, 2-3 sections, 3-5 sources
- standard: multi-pass reasoning, 5-7 sections, 5-10 sources
- deep: multi-pass with deeper analysis, 7-12 sections, 10-20 sources
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

# System prompt for the DeepSeek research agent
RESEARCH_SYSTEM_PROMPT = """You are a research analyst and knowledge synthesizer.
Given a research query, produce comprehensive structured findings.

You MUST respond with valid JSON only, using this exact schema:
{
  "executive_summary": "2-3 paragraph summary of findings",
  "sections": [
    {
      "heading": "Section Title",
      "content": "Detailed analysis in this section",
      "subpoints": ["Key point 1", "Key point 2"]
    }
  ],
  "key_insights": ["Insight 1", "Insight 2", "Insight 3"],
  "conflicting_viewpoints": [
    {
      "position": "Viewpoint A",
      "supporting": "Evidence or reasoning for this position"
    }
  ],
  "sources": [
    {
      "title": "Source title or description",
      "url": "(if applicable, otherwise describe source type)",
      "relevance": "Why this source matters"
    }
  ]
}

Guidelines:
- Be thorough but concise. Prioritize accurate, well-reasoned analysis.
- Include multiple perspectives on controversial topics.
- Cite real, verifiable sources when discussing specific claims.
- For theoretical questions, provide a balanced assessment of competing theories.
- Organize sections in logical flow: background → analysis → implications.
"""


class ResearchWorker(Worker):
    """Conducts deep research via DeepSeek and produces structured findings."""

    def __init__(
        self,
        input_queue: str = "research.tasks",
        output_queue: str = "research.synthesis",
        queue_dir: str = ".queues/coloring",
        api_key: str | None = None,
        api_base: str = "https://api.deepseek.com/v1",
        model: str = "deepseek-reasoner",
        use_api: bool = True,
    ):
        super().__init__(input_queue, output_queue, queue_dir)
        self.api_key = api_key or os.environ.get("FACTORY_DEEPSEEK_API_KEY", "")
        self.api_base = api_base
        self.model = model
        self.use_api = use_api and bool(self.api_key)

    @property
    def worker_name(self) -> str:
        return "research"

    def process(self, message: Message) -> Optional[Message]:
        """Research a query and return structured findings."""
        payload = message.payload
        query = payload.get("query", "")
        depth = payload.get("depth", "standard")
        max_sources = payload.get("max_sources", 5)

        if not query or len(query) < 10:
            raise FatalError(f"Query too short ({len(query)} chars, min 10)")

        if self.use_api:
            try:
                result = self._call_deepseek(query, depth, max_sources)
            except TransientError:
                raise
            except Exception as e:
                logger.warning("[research] DeepSeek API failed, using fallback: %s", e)
                result = self._template_fallback(query, depth)
        else:
            logger.info("[research] No API key, using template fallback")
            result = self._template_fallback(query, depth)

        # Build the findings payload for the synthesis stage
        findings_payload = {
            "request_id": message.trace_id,
            "query": query,
            "executive_summary": result.get("executive_summary", ""),
            "sections": result.get("sections", []),
            "sources": result.get("sources", []),
            "key_insights": result.get("key_insights", []),
            "conflicting_viewpoints": result.get("conflicting_viewpoints", []),
            "metadata": {
                "depth": depth,
                "model": self.model if self.use_api else "template",
                "generation_time_ms": result.get("_generation_time_ms", 0),
            },
        }

        return message.with_payload(
            findings_payload,
            new_type="research_synthesis",
        )

    def _call_deepseek(
        self, query: str, depth: str, max_sources: int
    ) -> dict:
        """Call DeepSeek chat completion API for research."""
        import httpx

        # Build the depth-appropriate user prompt
        depth_instructions = {
            "quick": "Provide a concise overview. 2-3 sections, 3-5 key points each.",
            "standard": "Provide comprehensive analysis. 5-7 sections with subpoints.",
            "deep": "Provide exhaustive deep analysis. 7-12 sections with detailed subpoints, multiple angles, and thorough source references.",
        }
        depth_note = depth_instructions.get(depth, depth_instructions["standard"])

        user_prompt = json.dumps({
            "query": query,
            "depth_instruction": depth_note,
            "max_sources": max_sources,
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
                        {"role": "system", "content": RESEARCH_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.5,
                    "max_tokens": 4096,
                },
                timeout=120.0,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]

            # Parse JSON from response
            result = json.loads(content)
            elapsed_ms = int((time.monotonic() - start) * 1000)
            result["_generation_time_ms"] = elapsed_ms
            return result

        except httpx.TimeoutException:
            raise TransientError("DeepSeek API timeout during research")
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (429, 502, 503):
                raise TransientError(f"DeepSeek API {e.response.status_code}")
            raise FatalError(f"DeepSeek API error: {e.response.status_code}")
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("[research] Failed to parse DeepSeek response: %s", e)
            return self._template_fallback(query, depth)

    def _template_fallback(self, query: str, depth: str) -> dict:
        """Produce structured findings without API calls."""
        sections = [
            {
                "heading": "Overview",
                "content": f"This section provides a general overview of: {query}.",
                "subpoints": ["Background context", "Current state of knowledge"],
            },
            {
                "heading": "Key Analysis",
                "content": f"A detailed analysis of the topic: {query}.",
                "subpoints": ["Primary factors", "Secondary considerations", "Notable patterns"],
            },
        ]

        if depth == "deep":
            sections.append({
                "heading": "Deep Analysis",
                "content": f"Extended analysis of: {query}",
                "subpoints": [
                    "Subtopic 1 analysis",
                    "Subtopic 2 analysis",
                    "Cross-cutting themes",
                ],
            })

        return {
            "executive_summary": (
                f"This research covers: {query}. "
                "Further details require DeepSeek API access with proper credentials."
            ),
            "sections": sections,
            "key_insights": [
                f"Key aspect 1 of: {query[:60]}",
                f"Key aspect 2 of: {query[:60]}",
                "Template mode — activate API for deeper insights",
            ],
            "conflicting_viewpoints": [],
            "sources": [
                {"title": f"Research on {query[:40]}", "url": "", "relevance": "Template fallback"},
            ],
            "_generation_time_ms": 0,
        }


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    worker = ResearchWorker(use_api=bool(os.environ.get("FACTORY_DEEPSEEK_API_KEY")))
    worker.start()
