"""ChimeraX-specific worker implementations using QRunnable and QThreadPool."""

from typing import TYPE_CHECKING, Any, Callable, Optional, Union

try:
    from Qt.QtCore import QObject, QRunnable, QThreadPool, Signal
    from Qt.QtGui import QImage, QPixmap

    QT_AVAILABLE = True
except ImportError:
    try:
        from qtpy.QtCore import QObject, QRunnable, QThreadPool, Signal
        from qtpy.QtGui import QImage, QPixmap

        QT_AVAILABLE = True
    except ImportError:
        QT_AVAILABLE = False

        # Fallback classes
        class QRunnable:
            def run(self):
                pass

        class QThreadPool:
            def start(self, runnable):
                pass

            def clear(self):
                pass

            def waitForDone(self, timeout):
                pass

        class QObject:
            pass

        class Signal:
            def __init__(self, *args):
                pass

            def emit(self, *args):
                pass

            def connect(self, func):
                pass


from .base import AbstractThumbnailWorker
from .data_worker import AbstractDataWorker

if TYPE_CHECKING:
    from copick.models import CopickRun, CopickTomogram


class ChimeraXWorkerSignals(QObject):
    """ChimeraX-specific worker signals."""

    thumbnail_loaded = Signal(str, object, object)  # thumbnail_id, pixmap, error
    data_loaded = Signal(str, object, object)  # data_type, data, error


# Create a compatible metaclass to resolve QRunnable + ABC metaclass conflict
class CompatibleMeta(type(AbstractThumbnailWorker), type(QRunnable)):
    """Metaclass that resolves conflicts between ABC and Qt metaclasses."""

    pass


class CompatibleDataMeta(type(AbstractDataWorker), type(QRunnable)):
    """Metaclass that resolves conflicts between ABC and Qt metaclasses for data workers."""

    pass


class ChimeraXThumbnailWorker(AbstractThumbnailWorker, QRunnable, metaclass=CompatibleMeta):
    """ChimeraX-specific thumbnail worker using QRunnable with unified caching."""

    def __init__(
        self,
        signals: ChimeraXWorkerSignals,
        item: Union["CopickRun", "CopickTomogram"],
        thumbnail_id: str,
        force_regenerate: bool = False,
    ):
        # Initialize AbstractThumbnailWorker first with a callback that uses signals
        def callback(tid: str, pixmap: Optional[Any], error: Optional[str]) -> None:
            """Callback that emits signal."""
            self.signals.thumbnail_loaded.emit(tid, pixmap, error)

        AbstractThumbnailWorker.__init__(self, item, thumbnail_id, callback, force_regenerate)
        QRunnable.__init__(self)
        self.signals = signals
        self._cancelled = False

    def start(self) -> None:
        """Start method for compatibility - actual start is via QThreadPool."""
        pass

    def cancel(self) -> None:
        """Cancel the thumbnail loading work."""
        self._cancelled = True

    def run(self) -> None:
        """Run method called by QThreadPool."""
        if self._cancelled:
            return

        try:
            # Use unified thumbnail generation with caching
            pixmap, error = self.generate_thumbnail_pixmap()
            self.signals.thumbnail_loaded.emit(self.thumbnail_id, pixmap, error)

        except Exception as e:
            self.signals.thumbnail_loaded.emit(self.thumbnail_id, None, str(e))

    def _setup_cache_image_interface(self) -> None:
        """Set up ChimeraX-specific image interface for caching."""
        if self._cache:
            try:
                from ..core.image_interface import QtImageInterface

                self._cache.set_image_interface(QtImageInterface())
            except Exception as e:
                print(f"Warning: Could not set up ChimeraX image interface: {e}")

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


class ChimeraXDataWorker(AbstractDataWorker, QRunnable, metaclass=CompatibleDataMeta):
    """ChimeraX-specific data worker using QRunnable."""

    def __init__(
        self,
        signals: ChimeraXWorkerSignals,
        run: "CopickRun",
        data_type: str,
    ):
        # Initialize AbstractDataWorker first with a callback that uses signals
        def callback(dtype: str, data: Optional[Any], error: Optional[str]) -> None:
            """Callback that emits signal."""
            self.signals.data_loaded.emit(dtype, data, error)

        AbstractDataWorker.__init__(self, run, data_type, callback)
        QRunnable.__init__(self)
        self.signals = signals

    def start(self) -> None:
        """Start method for compatibility - actual start is via QThreadPool."""
        pass

    def cancel(self) -> None:
        """Cancel the data loading work."""
        self._cancelled = True

    def run(self) -> None:
        """Run method called by QThreadPool."""
        if self._cancelled:
            return

        try:
            # Use base class data loading logic
            data, error = self.load_data()
            self.signals.data_loaded.emit(self.data_type, data, error)

        except Exception as e:
            self.signals.data_loaded.emit(self.data_type, None, str(e))


class ChimeraXWorkerManager:
    """Manages ChimeraX thumbnail and data workers using QThreadPool."""

    def __init__(self):
        if QT_AVAILABLE:
            self._thread_pool = QThreadPool()
            self._thread_pool.setMaxThreadCount(16)
        else:
            self._thread_pool = None

        self._signals = ChimeraXWorkerSignals()
        self._active_workers = []

    def start_thumbnail_worker(
        self,
        item: Union["CopickRun", "CopickTomogram"],
        thumbnail_id: str,
        callback: Callable[[str, Optional[Any], Optional[str]], None],
        force_regenerate: bool = False,
    ) -> None:
        """Start a thumbnail loading worker for either a run or specific tomogram."""
        if not QT_AVAILABLE or not self._thread_pool:
            callback(thumbnail_id, None, "Qt not available")
            return

        # Create unique signals for each worker to avoid callback conflicts
        worker_signals = ChimeraXWorkerSignals()
        worker_signals.thumbnail_loaded.connect(callback)

        worker = ChimeraXThumbnailWorker(worker_signals, item, thumbnail_id, force_regenerate)
        self._active_workers.append(worker)
        self._thread_pool.start(worker)

    def start_data_worker(
        self,
        run: "CopickRun",
        data_type: str,
        callback: Callable[[str, Optional[Any], Optional[str]], None],
    ) -> None:
        """Start a data loading worker for the specified data type."""
        if not QT_AVAILABLE or not self._thread_pool:
            callback(data_type, None, "Qt not available")
            return

        # Create unique signals for each worker to avoid callback conflicts
        worker_signals = ChimeraXWorkerSignals()
        worker_signals.data_loaded.connect(callback)

        worker = ChimeraXDataWorker(worker_signals, run, data_type)
        self._active_workers.append(worker)
        self._thread_pool.start(worker)

    def clear_workers(self) -> None:
        """Clear all pending workers."""
        for worker in self._active_workers:
            worker.cancel()
        self._active_workers.clear()

        if self._thread_pool:
            self._thread_pool.clear()

    def shutdown_workers(self, timeout_ms: int = 3000) -> None:
        """Shutdown all workers with timeout."""
        self.clear_workers()

        if self._thread_pool:
            self._thread_pool.waitForDone(timeout_ms)
