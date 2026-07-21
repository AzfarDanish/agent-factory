"""Abstract base class for artifact storage backends."""

from abc import ABC, abstractmethod


class Storage(ABC):
    """Storage interface for generated artifacts (images)."""

    @abstractmethod
    def save(self, artifact: bytes, path: str) -> str:
        """Persist an artifact and return its absolute path.
        
        Args:
            artifact: Raw bytes of the artifact.
            path: Relative or absolute destination path.
            
        Returns:
            Absolute path to the saved artifact.
        """
        ...

    @abstractmethod
    def retrieve(self, path: str) -> bytes | None:
        """Load an artifact by path. Returns None if not found."""
        ...

    @abstractmethod
    def delete(self, path: str) -> bool:
        """Remove an artifact. Returns True if deleted, False if not found."""
        ...

    @abstractmethod
    def exists(self, path: str) -> bool:
        """Check if an artifact exists at the given path."""
        ...
