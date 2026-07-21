"""Abstract base class for all workers."""

from abc import ABC, abstractmethod


class Worker(ABC):
    """Worker lifecycle interface.

    Every worker reads from one input queue, processes, and writes to one
    output queue (or DLQ). Workers are stateless — all state lives in messages.
    """

    @abstractmethod
    def start(self) -> None:
        """Start the worker's processing loop.
        
        - Connects to input and output queues
        - Begins polling for messages
        - Sends heartbeats on interval
        - Blocks until shutdown is requested
        """
        ...

    @abstractmethod
    def process(self, message: bytes) -> bytes | None:
        """Process a single message.
        
        Args:
            message: Serialized input message.
            
        Returns:
            Serialized output message to publish, or None to skip publishing.
            
        Raises:
            TransientError: Retryable failure (rate limit, timeout).
            FatalError: Non-retryable failure (invalid input, bad config).
        """
        ...

    @abstractmethod
    def shutdown(self, force: bool = False) -> None:
        """Gracefully stop the worker.
        
        Args:
            force: If True, skip in-flight message processing and exit immediately.
        """
        ...

    @abstractmethod
    def health(self) -> dict:
        """Return worker health status.
        
        Returns:
            Dict with keys: status (healthy/degraded/down), uptime_seconds,
            messages_processed, last_error.
        """
        ...
