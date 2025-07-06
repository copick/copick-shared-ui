"""napari-specific worker implementations using @thread_worker decorator."""

from typing import TYPE_CHECKING, Any, Callable, Optional, Union

try:
    print("🔍 Napari Workers: Importing napari threading components")
    from napari.qt.threading import thread_worker
    from qtpy.QtCore import QObject, Signal
    from qtpy.QtGui import QImage, QPixmap

    NAPARI_AVAILABLE = True
    print("✅ Napari Workers: napari threading components imported successfully")
except ImportError as e:
    print(f"❌ Napari Workers: napari threading import failed: {e}")
    NAPARI_AVAILABLE = False
    print("✅ Napari Workers: Will skip napari-specific functionality")

if NAPARI_AVAILABLE:
    from .base import AbstractThumbnailWorker

if TYPE_CHECKING:
    from copick.models import CopickRun, CopickTomogram


if NAPARI_AVAILABLE:

    class NapariWorkerSignals(QObject):
        """napari-specific worker signals."""

        thumbnail_loaded = Signal(str, object, object)  # thumbnail_id, pixmap, error

    class NapariThumbnailWorker(AbstractThumbnailWorker):
        """napari-specific thumbnail worker using @thread_worker decorator with unified caching."""

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

        def start(self) -> None:
            """Start the thumbnail loading work using napari's thread_worker."""
            print(f"🚀 NapariWorker: Starting thumbnail work for '{self.thumbnail_id}'")

            if not NAPARI_AVAILABLE:
                print(f"❌ NapariWorker: napari not available for '{self.thumbnail_id}'")
                self.callback(self.thumbnail_id, None, "napari not available")
                return

            # Create the worker function
            @thread_worker
            def load_thumbnail():
                print(f"🔧 NapariWorker: Inside thread_worker for '{self.thumbnail_id}'")

                if self._cancelled:
                    print(f"⚠️ NapariWorker: Cancelled '{self.thumbnail_id}'")
                    return None, "Cancelled"

                try:
                    # Use unified thumbnail generation with caching
                    pixmap, error = self.generate_thumbnail_pixmap()

                    if error:
                        print(f"❌ NapariWorker: Error generating thumbnail for '{self.thumbnail_id}': {error}")
                        return None, error
                    else:
                        print(f"✅ NapariWorker: Successfully created thumbnail for '{self.thumbnail_id}'")
                        return pixmap, None

                except Exception as e:
                    print(f"💥 NapariWorker: Exception in worker for '{self.thumbnail_id}': {e}")
                    import traceback

                    traceback.print_exc()
                    return None, str(e)

            # Connect worker signals
            print(f"🔗 NapariWorker: Creating and connecting worker for '{self.thumbnail_id}'")
            worker = load_thumbnail()
            worker.returned.connect(self._on_worker_finished)
            worker.errored.connect(self._on_worker_error)

            # Store reference to worker
            self._worker_func = worker
            print(f"📦 NapariWorker: Worker stored for '{self.thumbnail_id}'")

            # Actually start the worker!
            print(f"▶️ NapariWorker: Starting worker execution for '{self.thumbnail_id}'")
            worker.start()

        def cancel(self) -> None:
            """Cancel the thumbnail loading work."""
            self._cancelled = True
            if self._worker_func:
                # napari workers don't have a direct cancel method
                # We rely on the _cancelled flag check
                pass

        def _on_worker_finished(self, result):
            """Handle worker completion."""
            if self._cancelled:
                return

            pixmap, error = result
            self.callback(self.thumbnail_id, pixmap, error)

        def _on_worker_error(self, error):
            """Handle worker error."""
            if self._cancelled:
                return

            self.callback(self.thumbnail_id, None, str(error))

        def _setup_cache_image_interface(self) -> None:
            """Set up napari-specific image interface for caching."""
            if self._cache:
                try:
                    from ..core.image_interface import QtImageInterface

                    self._cache.set_image_interface(QtImageInterface())
                except Exception as e:
                    print(f"Warning: Could not set up napari image interface: {e}")

        def _array_to_pixmap(self, array: Any) -> Optional[QPixmap]:
            """Convert numpy array to QPixmap."""
            if not NAPARI_AVAILABLE:
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

                    # Create QImage from array
                    qimage = QImage(array.data, width, height, bytes_per_line, QImage.Format_Grayscale8)

                    # Convert to QPixmap
                    pixmap = QPixmap.fromImage(qimage)
                    return pixmap

                elif array.ndim == 3 and array.shape[2] == 3:
                    # RGB image
                    height, width, channels = array.shape
                    bytes_per_line = width * channels

                    # Create QImage from array
                    qimage = QImage(array.data, width, height, bytes_per_line, QImage.Format_RGB888)

                    # Convert to QPixmap
                    pixmap = QPixmap.fromImage(qimage)
                    return pixmap

                else:
                    print(f"Unsupported array shape: {array.shape}")
                    return None

            except Exception as e:
                print(f"Error converting array to pixmap: {e}")
                return None

    class NapariWorkerManager:
        """Manages napari thumbnail workers."""

        def __init__(self):
            self._active_workers = []

        def start_thumbnail_worker(
            self,
            item: Union["CopickRun", "CopickTomogram"],
            thumbnail_id: str,
            callback: Callable[[str, Optional[Any], Optional[str]], None],
            force_regenerate: bool = False,
        ) -> None:
            """Start a thumbnail loading worker for either a run or specific tomogram."""
            worker = NapariThumbnailWorker(item, thumbnail_id, callback, force_regenerate)
            self._active_workers.append(worker)
            worker.start()

        def clear_workers(self) -> None:
            """Clear all pending workers."""
            for worker in self._active_workers:
                worker.cancel()
            self._active_workers.clear()

        def shutdown_workers(self, timeout_ms: int = 3000) -> None:
            """Shutdown all workers with timeout."""
            self.clear_workers()
            # napari workers don't have a shutdown mechanism like QThreadPool
            # The cancelled flag should handle cleanup
