"""Base worker manager with thread limiting functionality."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Union

if TYPE_CHECKING:
    from copick.models import CopickRun, CopickTomogram


class AbstractWorkerManager(ABC):
    """Abstract base class for worker managers with thread limiting."""

    def __init__(self, max_concurrent_workers: int = 8):
        """Initialize worker manager with concurrent worker limit.

        Args:
            max_concurrent_workers: Maximum number of workers that can run simultaneously.
                Default is 8 to balance performance and system stability with large projects.
        """
        self._max_concurrent = max_concurrent_workers
        self._active_workers = []
        self._pending_queue = []
        print(f"🎛️ {self.__class__.__name__}: Initialized with max {max_concurrent_workers} concurrent workers")

    def start_thumbnail_worker(
        self,
        item: Union["CopickRun", "CopickTomogram"],
        thumbnail_id: str,
        callback: Callable[[str, Optional[Any], Optional[str]], None],
        force_regenerate: bool = False,
    ) -> None:
        """Start a thumbnail loading worker (queued if at limit)."""
        worker_info = {
            "type": "thumbnail",
            "item": item,
            "thumbnail_id": thumbnail_id,
            "callback": callback,
            "force_regenerate": force_regenerate,
        }
        self._queue_or_start_worker(worker_info)

    def start_data_worker(
        self,
        run: "CopickRun",
        data_type: str,
        callback: Callable[[str, Optional[Any], Optional[str]], None],
    ) -> None:
        """Start a data loading worker (queued if at limit)."""
        worker_info = {
            "type": "data",
            "run": run,
            "data_type": data_type,
            "callback": callback,
        }
        self._queue_or_start_worker(worker_info)

    def _queue_or_start_worker(self, worker_info: Dict[str, Any]) -> None:
        """Queue worker or start immediately if under limit."""
        if len(self._active_workers) < self._max_concurrent:
            self._start_worker_from_info(worker_info)
        else:
            self._pending_queue.append(worker_info)
            print(
                f"⏳ {self.__class__.__name__}: Queued {worker_info['type']} worker (queue size: {len(self._pending_queue)})",
            )

    @abstractmethod
    def _create_thumbnail_worker(
        self,
        item: Union["CopickRun", "CopickTomogram"],
        thumbnail_id: str,
        callback: Callable[[str, Optional[Any], Optional[str]], None],
        force_regenerate: bool = False,
    ) -> Any:
        """Create a platform-specific thumbnail worker."""
        pass

    @abstractmethod
    def _create_data_worker(
        self,
        run: "CopickRun",
        data_type: str,
        callback: Callable[[str, Optional[Any], Optional[str]], None],
    ) -> Any:
        """Create a platform-specific data worker."""
        pass

    @abstractmethod
    def _start_worker(self, worker: Any) -> None:
        """Start a platform-specific worker."""
        pass

    def _start_worker_from_info(self, worker_info: Dict[str, Any]) -> None:
        """Create and start a worker from worker info."""
        if worker_info["type"] == "thumbnail":
            worker = self._create_thumbnail_worker(
                worker_info["item"],
                worker_info["thumbnail_id"],
                self._create_callback_wrapper(worker_info["callback"]),
                worker_info["force_regenerate"],
            )
        elif worker_info["type"] == "data":
            worker = self._create_data_worker(
                worker_info["run"],
                worker_info["data_type"],
                self._create_callback_wrapper(worker_info["callback"]),
            )
        else:
            print(f"❌ {self.__class__.__name__}: Unknown worker type: {worker_info['type']}")
            return

        self._active_workers.append(worker)
        self._start_worker(worker)
        print(
            f"🚀 {self.__class__.__name__}: Started {worker_info['type']} worker ({len(self._active_workers)}/{self._max_concurrent} active)",
        )

    def _create_callback_wrapper(self, original_callback: Callable) -> Callable:
        """Create a callback wrapper that handles worker completion and queue processing."""

        def wrapped_callback(*args, **kwargs):
            # Call the original callback
            original_callback(*args, **kwargs)

            # Process the completion in the main thread
            self._on_worker_completed()

        return wrapped_callback

    def _on_worker_completed(self) -> None:
        """Handle worker completion - remove from active list and start next queued worker."""
        # Clean up completed workers from active list
        self._active_workers = [w for w in self._active_workers if self._is_worker_active(w)]

        # Start next queued worker if any
        if self._pending_queue and len(self._active_workers) < self._max_concurrent:
            next_worker_info = self._pending_queue.pop(0)
            print(
                f"🔄 {self.__class__.__name__}: Starting next queued {next_worker_info['type']} worker (queue size: {len(self._pending_queue)})",
            )
            self._start_worker_from_info(next_worker_info)

    @abstractmethod
    def _is_worker_active(self, worker: Any) -> bool:
        """Check if a worker is still active."""
        pass

    @abstractmethod
    def _cancel_worker(self, worker: Any) -> None:
        """Cancel a specific worker."""
        pass

    def clear_workers(self) -> None:
        """Clear all active and pending workers."""
        # Cancel active workers
        for worker in self._active_workers:
            self._cancel_worker(worker)
        self._active_workers.clear()

        # Clear pending queue
        self._pending_queue.clear()
        print(f"🧹 {self.__class__.__name__}: Cleared all active and pending workers")

    def shutdown_workers(self, timeout_ms: int = 3000) -> None:
        """Shutdown all workers with timeout."""
        self.clear_workers()

    def get_status(self) -> Dict[str, Any]:
        """Get current worker manager status for debugging."""
        return {
            "active_workers": len(self._active_workers),
            "pending_queue": len(self._pending_queue),
            "max_concurrent": self._max_concurrent,
            "class_name": self.__class__.__name__,
        }

    def set_max_concurrent_workers(self, max_workers: int) -> None:
        """Update the maximum number of concurrent workers."""
        old_max = self._max_concurrent
        self._max_concurrent = max_workers
        print(f"🎛️ {self.__class__.__name__}: Updated max concurrent workers from {old_max} to {max_workers}")

        # If we increased the limit, try to start queued workers
        if max_workers > old_max:
            self._process_pending_queue()

    def _process_pending_queue(self) -> None:
        """Process pending queue to start workers if slots are available."""
        while self._pending_queue and len(self._active_workers) < self._max_concurrent:
            next_worker_info = self._pending_queue.pop(0)
            print(f"🔄 {self.__class__.__name__}: Starting queued {next_worker_info['type']} worker")
            self._start_worker_from_info(next_worker_info)
