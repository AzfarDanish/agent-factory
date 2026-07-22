"""Synthesis Worker — compiles research findings into a polished report.

Reads from the research.synthesis queue, takes structured findings, calls
DeepSeek to synthesize them into a cohesive document, saves the report to
disk, and writes metadata to the research.completed queue.
"""
from __future__ import annotations

import json
import os
import time
import hashlib
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from src.core.message import Message
from src.workers.base import Worker, TransientError, FatalError


logger = logging.getLogger(__name__)

# System prompt for the synthesis agent
SYNTHESIS_SYSTEM_PROMPT = """You are a professional report writer and document synthesizer.
Given structured research findings, produce a polished, well-organized report.

The report must be written in clear, professional Markdown with:
- A compelling title
- Executive summary at the top
- Well-organized sections with subsections
- Key insights highlighted
- Sources listed at the end

Guidelines:
- Write for an intelligent but non-specialist audience
- Use clear headings (## level for sections, ### for subsections)
- Keep paragraphs focused and concise (3-5 sentences max)
- Include data or quotes from sources where relevant
- Note conflicting viewpoints when they exist
- End with a conclusion that synthesizes the findings
"""


class SynthesisWorker(Worker):
    """Compiles research findings into a polished, saved report."""

    def __init__(
        self,
        input_queue: str = "research.synthesis",
        output_queue: str = "research.completed",
        queue_dir: str = ".queues/coloring",
        output_dir: str = "output/research",
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
        self.output_dir = Path(output_dir)

    @property
    def worker_name(self) -> str:
        return "synthesis"

    def process(self, message: Message) -> Optional[Message]:
        """Synthesize findings into a report and save it."""
        payload = message.payload
        query = payload.get("query", "")
        executive_summary = payload.get("executive_summary", "")
        sections = payload.get("sections", [])
        sources = payload.get("sources", [])
        key_insights = payload.get("key_insights", [])
        conflicting_viewpoints = payload.get("conflicting_viewpoints", [])
        meta = payload.get("metadata", {})

        # Determine output format (default markdown)
        # For now, hardcode markdown output
        output_format = "markdown"

        if self.use_api:
            try:
                report_content, title = self._synthesize_with_api(
                    query, executive_summary, sections, sources,
                    key_insights, conflicting_viewpoints,
                )
            except TransientError:
                raise
            except Exception as e:
                logger.warning("[synthesis] API synthesis failed, using template: %s", e)
                report_content, title = self._template_report(
                    query, executive_summary, sections, sources, key_insights,
                )
        else:
            logger.info("[synthesis] No API key, using template fallback")
            report_content, title = self._template_report(
                query, executive_summary, sections, sources, key_insights,
            )

        # Save the report
        file_path = self._save_report(report_content, title, message.trace_id)

        # Count words and sources
        word_count = len(report_content.split())
        source_count = len(sources)

        # Build completed result
        result_payload = {
            "request_id": message.trace_id,
            "query": query,
            "title": title,
            "report": report_content,
            "format": output_format,
            "sections": [s["heading"] for s in sections],
            "source_count": source_count,
            "word_count": word_count,
            "file_path": str(file_path),
            "metadata": {
                "model": self.model if self.use_api else "template",
                "research_time_ms": meta.get("generation_time_ms", 0),
                "synthesis_time_ms": meta.get("_synthesis_time_ms", 0),
                "depth": meta.get("depth", "standard"),
            },
        }

        return message.with_payload(result_payload, new_type="research_report")

    def _synthesize_with_api(
        self,
        query: str,
        executive_summary: str,
        sections: list[dict],
        sources: list[dict],
        key_insights: list[str],
        conflicting_viewpoints: list[dict],
    ) -> tuple[str, str]:
        """Call DeepSeek to synthesize findings into a polished report."""
        import httpx

        findings_json = json.dumps({
            "query": query,
            "executive_summary": executive_summary,
            "sections": sections,
            "sources": sources,
            "key_insights": key_insights,
            "conflicting_viewpoints": conflicting_viewpoints,
        }, indent=2)

        user_prompt = (
            "Synthesize the following research findings into a polished Markdown report:\n\n"
            f"{findings_json}"
        )

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
                        {"role": "system", "content": SYNTHESIS_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.7,
                    "max_tokens": 4096,
                },
                timeout=120.0,
            )
            response.raise_for_status()
            data = response.json()
            report_content = data["choices"][0]["message"]["content"]

            # Extract title as first # heading or use query
            title = self._extract_title(report_content, query)

            elapsed_ms = int((time.monotonic() - start) * 1000)
            # Store timing in meta for the result payload
            self._synthesis_time_ms = elapsed_ms

            return report_content, title

        except httpx.TimeoutException:
            raise TransientError("DeepSeek API timeout during synthesis")
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (429, 502, 503):
                raise TransientError(f"DeepSeek API {e.response.status_code}")
            raise FatalError(f"DeepSeek API error: {e.response.status_code}")

    def _template_report(
        self,
        query: str,
        executive_summary: str,
        sections: list[dict],
        sources: list[dict],
        key_insights: list[str],
    ) -> tuple[str, str]:
        """Build a report from template when API is unavailable."""
        title = f"Research Report: {query[:60]}"

        lines = [
            f"# {title}",
            "",
            f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
            f"**Query:** {query}",
            "",
            "## Executive Summary",
            "",
            executive_summary or f"A research report on: {query}",
            "",
        ]

        for section in sections:
            heading = section.get("heading", "Section")
            content = section.get("content", "")
            subpoints = section.get("subpoints", [])

            lines.append(f"## {heading}")
            lines.append("")
            lines.append(content)
            lines.append("")

            for sp in subpoints:
                lines.append(f"- {sp}")
            lines.append("")

        if key_insights:
            lines.append("## Key Insights")
            lines.append("")
            for insight in key_insights:
                lines.append(f"- {insight}")
            lines.append("")

        if sources:
            lines.append("## Sources")
            lines.append("")
            for src in sources:
                title_s = src.get("title", "Untitled")
                relevance = src.get("relevance", "")
                lines.append(f"- **{title_s}** — {relevance}")
            lines.append("")

        lines.append("---")
        lines.append("*Report generated by AI Factory — template mode*")

        return "\n".join(lines), title

    def _extract_title(self, report: str, fallback_query: str) -> str:
        """Extract the first H1 heading from a markdown report."""
        for line in report.split("\n"):
            line = line.strip()
            if line.startswith("# ") and not line.startswith("## "):
                return line[2:].strip()
        return f"Research Report: {fallback_query[:60]}"

    def _save_report(self, content: str, title: str, trace_id: str) -> Path:
        """Save the report to disk."""
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        date_dir = self.output_dir / date_str
        date_dir.mkdir(parents=True, exist_ok=True)

        # Sanitize title for filename
        safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)
        safe_title = safe_title.strip()[:60]

        # Keep trace prefix for uniqueness
        file_name = f"{trace_id[:8]}_{safe_title}.md"
        if len(file_name) > 200:
            file_name = f"{trace_id[:8]}_{hashlib.md5(safe_title.encode()).hexdigest()[:8]}.md"

        file_path = date_dir / file_name
        file_path.write_text(content, encoding="utf-8")

        logger.info(
            "[synthesis] Report saved: %s (%d words, %d bytes)",
            file_path, len(content.split()), file_path.stat().st_size,
        )
        return file_path


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    worker = SynthesisWorker(use_api=bool(os.environ.get("FACTORY_DEEPSEEK_API_KEY")))
    worker.start()
