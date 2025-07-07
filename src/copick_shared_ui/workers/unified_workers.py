"""Unified worker implementations using thread_worker decorator for both napari and ChimeraX."""

from typing import TYPE_CHECKING, Any, Callable, Optional, Union

# Try napari first, then superqt
try:
    from napari.qt.threading import thread_worker

    THREAD_WORKER_SOURCE = "napari"
except ImportError:
    try:
        from superqt.utils._qthreading import thread_worker

        THREAD_WORKER_SOURCE = "superqt"
    except ImportError:
        thread_worker = None
        THREAD_WORKER_SOURCE = None

# Import Qt components
try:
    from qtpy.QtCore import QObject, Signal
    from qtpy.QtGui import QImage, QPixmap

    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False

if QT_AVAILABLE and thread_worker:
    from copick_shared_ui.workers.base import AbstractThumbnailWorker
    from copick_shared_ui.workers.base_manager import AbstractWorkerManager
    from copick_shared_ui.workers.data_worker import AbstractDataWorker

if TYPE_CHECKING:
    from copick.models import CopickRun, CopickTomogram


def is_threading_available() -> bool:
    """Check if threading is available."""
    return QT_AVAILABLE and thread_worker is not None


def get_threading_source() -> Optional[str]:
    """Get the source of the thread_worker decorator."""
    return THREAD_WORKER_SOURCE


if is_threading_available():

    class UnifiedThumbnailWorker(AbstractThumbnailWorker):
        """Unified thumbnail worker using @thread_worker decorator with caching."""

        def __init__(
            self,
            item: Union["CopickRun", "CopickTomogram"],
            thumbnail_id: str,
            callback: Callable[[str, Optional[Any], Optional[str]], None],
            force_regenerate: bool = False,
        ):
            super().__init__(item, thumbnail_id, callback, force_regenerate)
            self._worker_func = None
            self._cancelled = False
            self._finished = False

        def start(self) -> None:
            """Start the thumbnail loading work using thread_worker."""

            # Create the worker function as a generator for better control
            @thread_worker
            def load_thumbnail():
                # Check cancellation before starting
                if self._cancelled:
                    print(f"⚠️ Worker: Cancelled '{self.thumbnail_id}' before starting")
                    return None, "Cancelled"

                try:
                    # Yield to allow interruption
                    yield "Starting thumbnail generation..."

                    # Check cancellation again
                    if self._cancelled:
                        print(f"⚠️ Worker: Cancelled '{self.thumbnail_id}' during execution")
                        return None, "Cancelled"

                    # Use the shared caching system from AbstractThumbnailWorker
                    yield "Using shared caching system..."
                    if self._cancelled:
                        return None, "Cancelled"

                    # Call the parent's generate_thumbnail_pixmap method which handles all caching logic
                    pixmap, error = self.generate_thumbnail_pixmap()

                    if self._cancelled:
                        return None, "Cancelled"

                    if error:
                        return None, error

                    return pixmap, None

                except Exception as e:
                    print(f"💥 Worker: Exception in worker for '{self.thumbnail_id}': {e}")
                    import traceback

                    traceback.print_exc()
                    return None, str(e)

            # Connect worker signals
            worker = load_thumbnail()
            worker.returned.connect(self._on_worker_finished)
            worker.errored.connect(self._on_worker_error)

            # Store reference to worker
            self._worker_func = worker

            # Start the worker
            worker.start()

        def cancel(self) -> None:
            """Cancel the thumbnail loading work."""
            self._cancelled = True

            if self._worker_func:
                # Use the quit method to abort the worker
                if hasattr(self._worker_func, "quit"):
                    self._worker_func.quit()
                else:
                    print(f"⚠️ Worker: Worker for '{self.thumbnail_id}' has no quit method")

        def _on_worker_finished(self, result):
            """Handle worker completion with low-priority callback to prevent event loop flooding."""
            self._finished = True
            if self._cancelled:
                return

            pixmap, error = result

            # Use immediate callback for unified worker - platform-specific optimizations
            # are handled in the respective platform workers (ChimeraX, napari)
            self.callback(self.thumbnail_id, pixmap, error)

        def _on_worker_error(self, error):
            """Handle worker error."""
            if self._cancelled:
                return

            self.callback(self.thumbnail_id, None, str(error))

        def _setup_cache_image_interface(self) -> None:
            """Set up platform-specific image interface for caching."""
            if self._cache:
                try:
                    from copick_shared_ui.core.image_interface import QtImageInterface

                    self._cache.set_image_interface(QtImageInterface())
                except Exception as e:
                    print(f"Warning: Could not set up image interface: {e}")

        def _array_to_pixmap(self, array: Any) -> Optional[QPixmap]:
            """Convert numpy array to QPixmap."""
            if not QT_AVAILABLE:
                return None

            try:
                import numpy as np

                # Ensure array is uint8
                if array.dtype != np.uint8:
                    # Normalize to 0-255 range
                    array_min, array_max = array.min(), array.max()
                    if array_max > array_min:
                        array = ((array - array_min) / (array_max - array_min) * 255).astype(np.uint8)
                    else:
                        array = np.zeros_like(array, dtype=np.uint8)

                if array.ndim == 2:
                    # Grayscale image
                    height, width = array.shape
                    bytes_per_line = width
                    qimage = QImage(array.data, width, height, bytes_per_line, QImage.Format_Grayscale8)
                    pixmap = QPixmap.fromImage(qimage)
                    return pixmap

                elif array.ndim == 3 and array.shape[2] == 3:
                    # RGB image
                    height, width, channels = array.shape
                    bytes_per_line = width * channels
                    qimage = QImage(array.data, width, height, bytes_per_line, QImage.Format_RGB888)
                    pixmap = QPixmap.fromImage(qimage)
                    return pixmap

                else:
                    print(f"Unsupported array shape: {array.shape}")
                    return None

            except Exception as e:
                print(f"Error converting array to pixmap: {e}")
                return None

    class UnifiedDataWorker(AbstractDataWorker):
        """Unified data worker using @thread_worker decorator."""

        def __init__(
            self,
            run: "CopickRun",
            data_type: str,
            callback: Callable[[str, Optional[Any], Optional[str]], None],
        ):
            super().__init__(run, data_type, callback)
            self._worker_func = None
            self._finished = False

        def start(self) -> None:
            """Start the data loading work using thread_worker."""
            # Capture variables for the worker function
            worker_self = self  # Capture self for the worker closure
            worker_data_type = self.data_type
            worker_cancelled = lambda: self._cancelled  # noqa: E731

            # Create the worker function as a generator for better control
            @thread_worker
            def load_data():
                if worker_cancelled():
                    print(f"⚠️ DataWorker: Cancelled '{worker_data_type}' before starting")
                    return None, "Cancelled"

                try:
                    # Yield to allow interruption
                    yield f"Starting {worker_data_type} loading..."

                    # Check cancellation again
                    if worker_cancelled():
                        print(f"⚠️ DataWorker: Cancelled '{worker_data_type}' during execution")
                        return None, "Cancelled"

                    # Use the base class load_data method which handles all the logic
                    data, error = worker_self.load_data()

                    if worker_cancelled():
                        return None, "Cancelled"

                    return data, error

                except Exception as e:
                    import traceback

                    traceback.print_exc()
                    return None, str(e)

            # Connect worker signals
            worker = load_data()
            worker.returned.connect(self._on_worker_finished)
            worker.errored.connect(self._on_worker_error)

            # Store reference to worker
            self._worker_func = worker

            # Start the worker
            worker.start()

        def cancel(self) -> None:
            """Cancel the data loading work."""
            self._cancelled = True
            if self._worker_func:
                # Use the quit method to abort the worker
                if hasattr(self._worker_func, "quit"):
                    self._worker_func.quit()
                else:
                    print(f"⚠️ DataWorker: Worker for '{self.data_type}' has no quit method")

        def _on_worker_finished(self, result):
            """Handle worker completion."""
            self._finished = True
            if self._cancelled:
                return

            data, error = result
            self.callback(self.data_type, data, error)

        def _on_worker_error(self, error):
            """Handle worker error."""
            self._finished = True
            if self._cancelled:
                return

            self.callback(self.data_type, None, str(error))

    class UnifiedWorkerManager(AbstractWorkerManager):
        """Unified worker manager for both napari and ChimeraX."""

        def __init__(self, max_concurrent_workers: int = 8):
            """Initialize unified worker manager.

            Args:
                max_concurrent_workers: Maximum number of workers that can run simultaneously.
            """
            super().__init__(max_concurrent_workers)

        def _create_thumbnail_worker(
            self,
            item: Union["CopickRun", "CopickTomogram"],
            thumbnail_id: str,
            callback: Callable[[str, Optional[Any], Optional[str]], None],
            force_regenerate: bool = False,
        ) -> UnifiedThumbnailWorker:
            """Create a unified thumbnail worker."""
            return UnifiedThumbnailWorker(item, thumbnail_id, callback, force_regenerate)

        def _create_data_worker(
            self,
            run: "CopickRun",
            data_type: str,
            callback: Callable[[str, Optional[Any], Optional[str]], None],
        ) -> UnifiedDataWorker:
            """Create a unified data worker."""
            return UnifiedDataWorker(run, data_type, callback)

        def _start_worker(self, worker: Union[UnifiedThumbnailWorker, UnifiedDataWorker]) -> None:
            """Start a unified worker."""
            worker.start()

        def _is_worker_active(self, worker: Union[UnifiedThumbnailWorker, UnifiedDataWorker]) -> bool:
            """Check if a unified worker is still active."""
            return (
                hasattr(worker, "_worker_func")
                and worker._worker_func is not None
                and hasattr(worker, "_finished")
                and not worker._finished
            )

        def _cancel_worker(self, worker: Union[UnifiedThumbnailWorker, UnifiedDataWorker]) -> None:
            """Cancel a unified worker."""
            worker.cancel()

else:
    # Fallback classes when threading is not available
    class UnifiedThumbnailWorker:
        def __init__(self, *args, **kwargs):
            pass

        def start(self):
            pass

        def cancel(self):
            pass

    class UnifiedDataWorker:
        def __init__(self, *args, **kwargs):
            pass

        def start(self):
            pass

        def cancel(self):
            pass

    class UnifiedWorkerManager:
        def __init__(self, *args, **kwargs):
            pass

        def start_thumbnail_worker(self, *args, **kwargs):
            pass

        def start_data_worker(self, *args, **kwargs):
            pass

        def clear_workers(self):
            pass

        def shutdown_workers(self, timeout_ms=3000):
            pass

        def get_status(self):
            return {
                "error": f"Threading not available - QT: {QT_AVAILABLE}, thread_worker: {thread_worker is not None}",
            }


# Convenience functions for platform detection
def create_worker_manager(max_concurrent_workers: int = 8) -> UnifiedWorkerManager:
    """Create a worker manager for the current platform."""
    return UnifiedWorkerManager(max_concurrent_workers)


def get_platform_info() -> dict:
    """Get information about the current threading platform."""
    return {
        "qt_available": QT_AVAILABLE,
        "thread_worker_available": thread_worker is not None,
        "thread_worker_source": THREAD_WORKER_SOURCE,
        "threading_available": is_threading_available(),
    }
