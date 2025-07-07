"""ChimeraX-specific worker implementations with enhanced UI responsiveness optimizations."""

from typing import TYPE_CHECKING, Any, Callable, Optional, Union

from copick_shared_ui.workers.unified_workers import (
    QT_AVAILABLE,
    UnifiedDataWorker,
    UnifiedWorkerManager,
    create_worker_manager,
    get_platform_info,
    is_threading_available,
    thread_worker,
)

if TYPE_CHECKING:
    from copick.models import CopickRun, CopickTomogram

if is_threading_available():
    from copick_shared_ui.workers.base import AbstractThumbnailWorker

    class ChimeraXThumbnailWorker(AbstractThumbnailWorker):
        """ChimeraX-specific thumbnail worker with enhanced UI responsiveness optimizations."""

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

            @thread_worker
            def load_thumbnail():
                if self._cancelled:
                    return None, "Cancelled"

                try:
                    yield "Starting ChimeraX thumbnail generation..."
                    if self._cancelled:
                        return None, "Cancelled"

                    pixmap, error = self.generate_thumbnail_pixmap()

                    if self._cancelled:
                        return None, "Cancelled"

                    return pixmap, error

                except Exception as e:
                    print(f"💥 ChimeraX Worker: Exception for '{self.thumbnail_id}': {e}")
                    return None, str(e)

            worker = load_thumbnail()
            worker.returned.connect(self._on_worker_finished)
            worker.errored.connect(self._on_worker_error)

            self._worker_func = worker
            worker.start()

        def cancel(self) -> None:
            """Cancel the thumbnail loading work."""
            self._cancelled = True

            # Cancel any pending timer callbacks
            if hasattr(self, "_callback_timers"):
                for timer in self._callback_timers[:]:
                    try:
                        if timer and hasattr(timer, "stop"):
                            timer.stop()
                        if timer in self._callback_timers:
                            self._callback_timers.remove(timer)
                    except (AttributeError, ValueError):
                        pass

            if self._worker_func and hasattr(self._worker_func, "quit"):
                self._worker_func.quit()

        def _on_worker_finished(self, result):
            """Handle worker completion with ChimeraX-specific UI responsiveness optimizations."""
            self._finished = True
            if self._cancelled:
                return

            pixmap, error = result

            # ChimeraX-specific optimizations to prevent UI blocking
            if QT_AVAILABLE:
                try:
                    from qtpy.QtCore import QTimer

                    timer = QTimer(None)
                    timer.setSingleShot(True)

                    if not hasattr(self, "_callback_timers"):
                        self._callback_timers = []
                    self._callback_timers.append(timer)

                    def execute_callback():
                        try:
                            if (
                                hasattr(self, "callback")
                                and hasattr(self, "thumbnail_id")
                                and self.callback is not None
                                and not self._cancelled
                            ):
                                self.callback(self.thumbnail_id, pixmap, error)
                        except (AttributeError, RuntimeError):
                            pass
                        finally:
                            try:
                                if hasattr(self, "_callback_timers") and timer in self._callback_timers:
                                    self._callback_timers.remove(timer)
                            except (AttributeError, ValueError):
                                pass

                    timer.timeout.connect(execute_callback)
                    # Use 0ms delay to defer callback to next event loop iteration
                    timer.start(5)
                except ImportError:
                    if not self._cancelled:
                        self.callback(self.thumbnail_id, pixmap, error)
            else:
                if not self._cancelled:
                    self.callback(self.thumbnail_id, pixmap, error)

        def _on_worker_error(self, error):
            """Handle worker error."""
            if not self._cancelled:
                self.callback(self.thumbnail_id, None, str(error))

else:
    # Fallback when threading is not available
    class ChimeraXThumbnailWorker:
        def __init__(self, *args, **kwargs):
            pass

        def start(self):
            pass

        def cancel(self):
            pass


# Re-export unified classes with ChimeraX naming for compatibility
ChimeraXDataWorker = UnifiedDataWorker
ChimeraXWorkerManager = UnifiedWorkerManager


# Convenience functions
def is_chimerax_threading_available() -> bool:
    """Check if ChimeraX threading is available."""
    return is_threading_available()


def get_chimerax_platform_info() -> dict:
    """Get ChimeraX threading platform information."""
    info = get_platform_info()
    info["platform"] = "ChimeraX"
    return info


def create_chimerax_worker_manager(max_concurrent_workers: int = 6) -> ChimeraXWorkerManager:
    """Create a ChimeraX worker manager with platform-appropriate defaults."""
    return create_worker_manager(max_concurrent_workers)
