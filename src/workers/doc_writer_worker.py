"""Doc Writer Worker — writes full documents from structured outlines.

Reads from the doc.write queue, takes the outline + topic, calls DeepSeek
to produce the full document content, saves to disk, and writes metadata
to the doc.completed queue.
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

WRITER_SYSTEM_PROMPT = """You are a technical writer and documentation specialist.
Given a document outline with sections, write the full document content.

Write in the specified tone:
- formal: Professional, precise, objective. Use third person.
- conversational: Friendly, approachable, direct. Use "you".
- technical: Dense, precise, assumes technical background. Use domain terminology.

Document structure rules:
- Start with a title (# level)
- Follow with an introductory paragraph
- Use ## for each section heading from the outline
- Use ### for subsections within a section
- Include code blocks with language tags when code_examples is true
- End with a conclusion or next steps section
- Add a "Further Reading" section if sources are available

Keep paragraphs focused (3-5 sentences). Use bullet lists for multiple items.
Write comprehensively but avoid filler — every paragraph should teach something.
"""


class DocWriterWorker(Worker):
    """Writes full documents from outlines via DeepSeek."""

    def __init__(
        self,
        input_queue: str = "doc.write",
        output_queue: str = "doc.completed",
        queue_dir: str = ".queues/coloring",
        output_dir: str = "output/docs",
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
        return "doc_writer"

    def process(self, message: Message) -> Optional[Message]:
        payload = message.payload
        topic = payload.get("topic", "")
        title = payload.get("title", topic)
        sections = payload.get("sections", [])
        doc_type = payload.get("document_type", "guide")
        output_format = payload.get("format", "markdown")
        tone = payload.get("tone", "formal")
        audience = payload.get("target_audience", "")
        prerequisites = payload.get("prerequisites", [])
        meta = payload.get("metadata", {})

        if not sections:
            raise FatalError("No sections in outline — cannot write document")

        if self.use_api:
            try:
                content = self._write_with_api(title, sections, tone, output_format)
            except TransientError:
                raise
            except Exception as e:
                logger.warning("[doc_writer] API failed, using template: %s", e)
                content = self._template_document(title, sections, tone, prerequisites)
        else:
            logger.info("[doc_writer] No API key, using template fallback")
            content = self._template_document(title, sections, tone, prerequisites)

        # Save to disk
        file_path = self._save_document(content, title, message.trace_id, doc_type)

        word_count = len(content.split())
        section_headings = [s.get("heading", "") for s in sections]

        result_payload = {
            "request_id": message.trace_id,
            "topic": topic,
            "title": title,
            "document_type": doc_type,
            "format": output_format,
            "content": content,
            "sections": section_headings,
            "word_count": word_count,
            "file_path": str(file_path),
            "metadata": {
                "model": self.model if self.use_api else "template",
                "outline_time_ms": meta.get("outline_time_ms", 0),
                "writing_time_ms": meta.get("_writing_time_ms", 0),
                "tone": tone,
            },
        }

        return message.with_payload(result_payload, new_type="doc_completed")

    def _write_with_api(self, title, sections, tone, output_format):
        import httpx

        outline_json = json.dumps({
            "title": title,
            "sections": sections,
            "output_format": output_format,
        }, indent=2)

        user_prompt = (
            f"Write a {tone}-toned document in {output_format} format "
            f"using this outline:\n\n{outline_json}"
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
                        {"role": "system", "content": WRITER_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.7,
                    "max_tokens": 4096,
                },
                timeout=120.0,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            self._writing_time_ms = int((time.monotonic() - start) * 1000)
            return content
        except httpx.TimeoutException:
            raise TransientError("DeepSeek API timeout")
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (429, 502, 503):
                raise TransientError(f"DeepSeek API {e.response.status_code}")
            raise FatalError(f"DeepSeek API error: {e.response.status_code}")

    def _template_document(self, title, sections, tone, prerequisites):
        lines = [
            f"# {title}",
            "",
            f"**Document Type:** {'Guide' if tone == 'formal' else tone.title()}",
            f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
            "",
        ]

        if prerequisites:
            lines.append("## Prerequisites")
            lines.append("")
            for p in prerequisites:
                lines.append(f"- {p}")
            lines.append("")

        for section in sections:
            heading = section.get("heading", "Section")
            description = section.get("description", "")
            key_points = section.get("key_points", [])
            code_examples = section.get("code_examples", False)

            lines.append(f"## {heading}")
            lines.append("")
            lines.append(description)
            lines.append("")

            if key_points:
                for kp in key_points:
                    lines.append(f"- {kp}")
                lines.append("")

            if code_examples:
                lines.append("```")
                lines.append(f"# Example for {heading.lower()}")
                lines.append("```")
                lines.append("")

        lines.append("## Next Steps")
        lines.append("")
        lines.append(f"This document covered the essentials of {title}. "
                     "Refer to related documentation for deeper dives into specific topics.")
        lines.append("")
        lines.append("---")
        lines.append(f"*Generated by AI Factory Documentation Pipeline — template mode*")

        return "\n".join(lines)

    def _save_document(self, content, title, trace_id, doc_type):
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        date_dir = self.output_dir / doc_type / date_str
        date_dir.mkdir(parents=True, exist_ok=True)

        safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)
        safe_title = safe_title.strip()[:60]

        file_name = f"{trace_id[:8]}_{safe_title}.md"
        if len(file_name) > 200:
            file_name = f"{trace_id[:8]}_{hashlib.md5(safe_title.encode()).hexdigest()[:8]}.md"

        file_path = date_dir / file_name
        file_path.write_text(content, encoding="utf-8")
        logger.info("[doc_writer] Saved: %s (%d words)", file_path, len(content.split()))
        return file_path


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    worker = DocWriterWorker(use_api=bool(os.environ.get("FACTORY_DEEPSEEK_API_KEY")))
    worker.start()
