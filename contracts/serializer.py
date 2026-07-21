"""Abstract base class for message serializers."""

from abc import ABC, abstractmethod


class Serializer(ABC):
    """Message serialization interface."""

    @abstractmethod
    def encode(self, message: dict) -> bytes:
        """Serialize a message dict to bytes for queue transport."""
        ...

    @abstractmethod
    def decode(self, data: bytes) -> dict:
        """Deserialize bytes from a queue back to a message dict."""
        ...
