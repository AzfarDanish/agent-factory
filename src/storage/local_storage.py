"""Storage — local filesystem persistence for generated images.

Handles saving generated images to disk with a deterministic naming convention
and directory structure organized by age group and date.
"""

import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from src.core.coloring_domain import AgeGroup


class LocalStorage:
    """Filesystem-based storage for generated coloring pages."""

    def __init__(self, base_dir: str | Path = "output"):
        self.base_dir = Path(base_dir)

    def save(self, artifact: bytes, age_group: str, request_id: str, style: str = "general") -> str:
        """Save a generated image and return its absolute path.

        Directory: output/{style}/{date}/{request_id}_{content_hash}.png
        """
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        content_hash = hashlib.sha256(artifact).hexdigest()[:12]

        subdir = self.base_dir / style / date_str
        subdir.mkdir(parents=True, exist_ok=True)

        file_name = f"{request_id[:12]}_{content_hash}.png"
        file_path = subdir / file_name

        file_path.write_bytes(artifact)
        return str(file_path.resolve())

    def retrieve(self, path: str) -> Optional[bytes]:
        """Load an artifact by its path."""
        p = Path(path)
        if p.exists():
            return p.read_bytes()
        return None

    def delete(self, path: str) -> bool:
        """Remove an artifact. Returns True if deleted."""
        p = Path(path)
        if p.exists():
            p.unlink()
            return True
        return False

    def exists(self, path: str) -> bool:
        """Check if an artifact exists."""
        return Path(path).exists()
