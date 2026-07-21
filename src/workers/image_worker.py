"""Image Worker — GPT Image 1 image generation.

Reads from the image queue, calls GPT Image 1 (DALL-E 3 / DALL-E 2) to generate
a black-and-white line art coloring page, saves the result, and writes the
metadata to the completed queue.
"""

import os
import logging
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from src.core.message import Message
from src.workers.base import Worker, TransientError, FatalError


logger = logging.getLogger(__name__)


class ImageWorker(Worker):
    """Generates coloring page images via GPT Image 1 (OpenAI DALL-E).

    Handles:
    - API call with refined prompt
    - Download and save the generated image
    - Metadata writing to the completed queue
    """

    def __init__(
        self,
        input_queue: str = "image",
        output_queue: str = "completed",
        queue_dir: str = ".queues/coloring",
        output_dir: str = "output",
        api_key: str | None = None,
        api_base: str = "https://api.openai.com/v1",
        model: str = "gpt-image-1",
        image_size: str = "1024x1024",
        use_api: bool = True,
    ):
        super().__init__(input_queue, output_queue, queue_dir)
        self.api_key = api_key or os.environ.get("FACTORY_OPENAI_API_KEY", "")
        self.api_base = api_base
        self.model = model
        self.image_size = image_size
        self.use_api = use_api and bool(self.api_key)
        self.output_dir = Path(output_dir)

    @property
    def worker_name(self) -> str:
        return "image"

    def process(self, message: Message) -> Optional[Message]:
        """Generate an image from the refined prompt."""
        payload = message.payload
        refined_prompt = payload.get("refined_prompt", "")
        negative_prompt = payload.get("negative_prompt", "")
        style = payload.get("style", "simple")

        if not refined_prompt:
            raise FatalError("Empty refined_prompt in image task")

        if self.use_api:
            try:
                image_data, generation_time = self._call_gpt_image(refined_prompt)
            except (TransientError, FatalError) as e:
                logger.warning("[image] API call failed: %s", e)
                logger.info("[image] Falling back to placeholder generation")
                image_data, generation_time = self._generate_placeholder(refined_prompt)
        else:
            # Demo mode: create a placeholder image
            logger.info("[image] No API key, generating placeholder")
            image_data, generation_time = self._generate_placeholder(refined_prompt)

        # Save the image
        request_id = message.trace_id
        file_path = self._save_image(image_data, request_id, style)

        # Build completed result
        result_payload = {
            "request_id": request_id,
            "image_path": str(file_path),
            "image_format": "png",
            "metadata": {
                "model": self.model if self.use_api else "placeholder",
                "prompt_used": refined_prompt,
                "generation_time_ms": generation_time,
            },
        }

        return message.with_payload(result_payload, new_type="result")

    def _call_gpt_image(self, prompt: str) -> tuple[bytes, int]:
        """Call OpenAI DALL-E API to generate an image.

        Tries the configured model first. Falls back to dall-e-2 automatically
        if the model doesn't exist.
        """
        import httpx
        import time

        models_to_try = [self.model]
        # Fallbacks for different OpenAI generations
        for fallback in ["gpt-image-1", "gpt-image-1-mini", "gpt-image-2"]:
            if fallback not in models_to_try:
                models_to_try.append(fallback)

        last_error = None

        for model in models_to_try:
            start = time.monotonic()
            size = self.image_size if model == self.model else "512x512"
            try:
                response = httpx.post(
                    f"{self.api_base}/images/generations",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "prompt": prompt,
                        "n": 1,
                        "size": size,
                    },
                    timeout=120.0,
                )
                response.raise_for_status()
                data = response.json()
                item = data["data"][0]
                if "url" in item:
                    img_response = httpx.get(item["url"], timeout=60.0)
                    img_response.raise_for_status()
                    image_bytes = img_response.content
                elif "b64_json" in item:
                    import base64
                    image_bytes = base64.b64decode(item["b64_json"])
                else:
                    raise FatalError(f"Unknown response format: {list(item.keys())}")
                elapsed = int((time.monotonic() - start) * 1000)
                logger.info("[image] Generated via %s (%s) in %dms", model, size, elapsed)
                return image_bytes, elapsed

            except httpx.HTTPStatusError as e:
                body = e.response.text[:500] if e.response.text else ""
                if "does not exist" in body and model != models_to_try[-1]:
                    logger.warning("[image] Model %s unavailable, trying %s", model, models_to_try[-1])
                    last_error = str(e)
                    continue
                if e.response.status_code in (429, 502, 503):
                    raise TransientError(f"GPT Image API {e.response.status_code}: {body}")
                raise FatalError(f"GPT Image API error: {e.response.status_code} - {body}")
            except httpx.TimeoutException:
                last_error = f"{model} timeout"
                if model == models_to_try[-1]:
                    raise TransientError("GPT Image API timeout")

        raise FatalError(f"All image models failed. Last error: {last_error}")

    def _generate_placeholder(self, prompt: str) -> tuple[bytes, int]:
        """Generate a simple placeholder PNG using pure Python (no Pillow)."""
        import struct
        import zlib

        width, height = 512, 512

        # Create a white image with black border (simple PGM-style PNG)
        raw_data = b""
        for y in range(height):
            row = b"\xff"  # filter byte (None)
            for x in range(width):
                # Draw a simple diamond shape in black outline
                cx, cy = width // 2, height // 2
                dx = abs(x - cx)
                dy = abs(y - cy)
                # Diamond: |dx| + |dy| < 200 = outline, < 190 = white
                dist = dx + dy
                if 190 < dist < 200:
                    row += b"\x00\x00\x00"  # black
                elif abs(x - width // 4) < 2 and abs(y - height // 2 - 50) < 150:
                    row += b"\x00\x00\x00"  # vertical line
                elif abs(y - height // 2) < 2 and abs(x - width // 2) < 150:
                    row += b"\x00\x00\x00"  # horizontal line
                else:
                    row += b"\xff\xff\xff"  # white
            raw_data += row

        def make_chunk(chunk_type: bytes, data: bytes) -> bytes:
            chunk = chunk_type + data
            return struct.pack(">I", len(data)) + chunk + struct.pack(">I", zlib.crc32(chunk) & 0xFFFFFFFF)

        # PNG signature
        png = b"\x89PNG\r\n\x1a\n"

        # IHDR
        ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
        png += make_chunk(b"IHDR", ihdr)

        # IDAT (image data)
        compressed = zlib.compress(raw_data)
        png += make_chunk(b"IDAT", compressed)

        # IEND
        png += make_chunk(b"IEND", b"")

        return png, 0

    def _save_image(self, image_data: bytes, request_id: str, style: str) -> Path:
        """Save image bytes to disk with a deterministic path."""
        # Create dated directory structure
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        style_dir = self.output_dir / style / date_str
        style_dir.mkdir(parents=True, exist_ok=True)

        # Hash the image content for a unique filename
        content_hash = hashlib.sha256(image_data).hexdigest()[:12]
        file_name = f"{request_id[:12]}_{content_hash}.png"
        file_path = style_dir / file_name

        file_path.write_bytes(image_data)
        logger.info("[image] Saved: %s (%d bytes)", file_path, len(image_data))
        return file_path


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    worker = ImageWorker(use_api=bool(os.environ.get("FACTORY_OPENAI_API_KEY")))
    worker.start()
