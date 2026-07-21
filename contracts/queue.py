"""Abstract base class for all queue backends."""

from abc import ABC, abstractmethod


class Queue(ABC):
    """Message queue interface.

    All queue backends implement this contract. Messages are opaque bytes
    — serialization is handled by the serializer contract.
    """

    @abstractmethod
    def connect(self) -> None:
        """Open connection to the queue backend.
        
        Raises ConnectionError if the backend is unreachable.
        """
        ...

    @abstractmethod
    def publish(self, queue_name: str, message: bytes) -> None:
        """Publish a message to a queue.
        
        Args:
            queue_name: Logical queue name (e.g. 'coloring.reasoning').
            message: Serialized message bytes.
            
        Raises:
            QueueWriteError: If the write fails.
        """
        ...

    @abstractmethod
    def consume(self, queue_name: str, timeout: float = 1.0) -> bytes | None:
        """Read one message from a queue (non-destructive).
        
        Args:
            queue_name: Logical queue name.
            timeout: Max seconds to wait for a message.
            
        Returns:
            Message bytes, or None if the queue is empty and timeout expires.
        """
        ...

    @abstractmethod
    def acknowledge(self, queue_name: str, message_id: str) -> None:
        """Remove a message from the queue after successful processing.
        
        Args:
            queue_name: Logical queue name.
            message_id: The message ID to acknowledge.
        """
        ...

    @abstractmethod
    def requeue(self, queue_name: str, message: bytes, delay_seconds: float = 0) -> None:
        """Re-publish a message (for retry after transient failure).
        
        Args:
            queue_name: Logical queue name (typically the original queue or its DLQ).
            message: Serialized message bytes.
            delay_seconds: Minimum delay before the message is visible again.
        """
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection and release resources."""
        ...

    @abstractmethod
    def queue_length(self, queue_name: str) -> int:
        """Return the number of pending messages in a queue."""
        ...
