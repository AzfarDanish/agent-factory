"""Abstract base class for the pipeline orchestrator."""

from abc import ABC, abstractmethod


class Orchestrator(ABC):
    """Orchestration interface.

    The orchestrator manages the pipeline: it reads from input queues,
    validates messages, routes them to the next stage via the state machine,
    and handles errors. Hermes Agent is the primary orchestrator host.
    """

    @abstractmethod
    def start_pipeline(self) -> None:
        """Begin the main orchestration loop.
        
        - Initialize all queue connections
        - Start polling the requests queue
        - Route messages through the state machine
        - Block until shutdown
        """
        ...

    @abstractmethod
    def route_message(self, message: bytes, source_queue: str) -> str | None:
        """Determine the target queue for a message.
        
        Args:
            message: Serialized message from the source queue.
            source_queue: Name of the queue the message came from.
            
        Returns:
            Target queue name, or None if the message terminates (completed/failed).
        """
        ...

    @abstractmethod
    def handle_error(self, message: bytes, error: Exception, source_queue: str) -> None:
        """Classify and route an error.
        
        Transient errors go back to the source queue (retry).
        Fatal errors go to the DLQ.
        Infrastructure errors raise immediately.
        """
        ...

    @abstractmethod
    def shutdown(self) -> None:
        """Stop the pipeline gracefully."""
        ...
