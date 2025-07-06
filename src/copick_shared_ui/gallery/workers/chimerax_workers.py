"""ChimeraX-specific worker implementations using QRunnable and QThreadPool."""

from typing import Any, Callable, Optional, TYPE_CHECKING

try:
    from qtpy.QtCore import QRunnable, QThreadPool, QObject, Signal
    from qtpy.QtGui import QPixmap, QImage
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False
    # Fallback classes
    class QRunnable:
        def run(self): pass
    class QThreadPool:
        def start(self, runnable): pass
        def clear(self): pass
        def waitForDone(self, timeout): pass
    class QObject:
        pass
    class Signal:
        def __init__(self, *args): pass
        def emit(self, *args): pass
        def connect(self, func): pass

from .base_workers import AbstractThumbnailWorker

if TYPE_CHECKING:
    from copick.models import CopickRun


class ChimeraXWorkerSignals(QObject):
    """ChimeraX-specific worker signals."""
    
    thumbnail_loaded = Signal(str, object, object)  # thumbnail_id, pixmap, error


# Create a compatible metaclass to resolve QRunnable + ABC metaclass conflict
class CompatibleMeta(type(AbstractThumbnailWorker), type(QRunnable)):
    """Metaclass that resolves conflicts between ABC and Qt metaclasses."""
    pass


class ChimeraXThumbnailWorker(QRunnable, AbstractThumbnailWorker, metaclass=CompatibleMeta):
    """ChimeraX-specific thumbnail worker using QRunnable."""
    
    def __init__(
        self,
        signals: ChimeraXWorkerSignals,
        run: "CopickRun",
        thumbnail_id: str,
        force_regenerate: bool = False
    ):
        QRunnable.__init__(self)
        AbstractThumbnailWorker.__init__(self, run, thumbnail_id, None, force_regenerate)
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
            # Select best tomogram
            tomogram = self._select_best_tomogram(self.run)
            if not tomogram:
                self.signals.thumbnail_loaded.emit(self.thumbnail_id, None, "No tomogram found")
                return
                
            # Generate thumbnail array
            thumbnail_array = self._generate_thumbnail_array(tomogram)
            if thumbnail_array is None:
                self.signals.thumbnail_loaded.emit(self.thumbnail_id, None, "Failed to generate thumbnail")
                return
                
            # Convert to QPixmap
            pixmap = self._array_to_pixmap(thumbnail_array)
            if pixmap is None:
                self.signals.thumbnail_loaded.emit(self.thumbnail_id, None, "Failed to convert to pixmap")
                return
                
            self.signals.thumbnail_loaded.emit(self.thumbnail_id, pixmap, None)
            
        except Exception as e:
            self.signals.thumbnail_loaded.emit(self.thumbnail_id, None, str(e))
            
    def _array_to_pixmap(self, array: Any) -> Optional[QPixmap]:
        """Convert numpy array to QPixmap."""
        try:
            import numpy as np
            
            if array.ndim == 2:
                # Grayscale image
                height, width = array.shape
                bytes_per_line = width
                
                # Create QImage from array
                qimage = QImage(
                    array.data,
                    width,
                    height,
                    bytes_per_line,
                    QImage.Format_Grayscale8
                )
                
                # Convert to QPixmap
                pixmap = QPixmap.fromImage(qimage)
                return pixmap
                
            elif array.ndim == 3 and array.shape[2] == 3:
                # RGB image
                height, width, channels = array.shape
                bytes_per_line = width * channels
                
                # Create QImage from array
                qimage = QImage(
                    array.data,
                    width,
                    height,
                    bytes_per_line,
                    QImage.Format_RGB888
                )
                
                # Convert to QPixmap
                pixmap = QPixmap.fromImage(qimage)
                return pixmap
                
            else:
                print(f"Unsupported array shape: {array.shape}")
                return None
                
        except Exception as e:
            print(f"Error converting array to pixmap: {e}")
            return None


class ChimeraXWorkerManager:
    """Manages ChimeraX thumbnail workers using QThreadPool."""
    
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
        run: "CopickRun",
        thumbnail_id: str,
        callback: Callable[[str, Optional[Any], Optional[str]], None],
        force_regenerate: bool = False
    ) -> None:
        """Start a thumbnail loading worker."""
        if not QT_AVAILABLE or not self._thread_pool:
            callback(thumbnail_id, None, "Qt not available")
            return
            
        # Connect callback to signals
        self._signals.thumbnail_loaded.connect(callback)
        
        worker = ChimeraXThumbnailWorker(self._signals, run, thumbnail_id, force_regenerate)
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