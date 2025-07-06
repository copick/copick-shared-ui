"""napari-specific worker implementations using @thread_worker decorator."""

print("🔍 Napari Workers: Starting import")

from typing import Any, Callable, Optional, TYPE_CHECKING
from functools import wraps

try:
    print("🔍 Napari Workers: Importing napari threading components")
    from napari.qt.threading import thread_worker
    from qtpy.QtGui import QPixmap, QImage
    from qtpy.QtCore import QObject, Signal
    NAPARI_AVAILABLE = True
    print("✅ Napari Workers: napari threading components imported successfully")
except ImportError as e:
    print(f"❌ Napari Workers: napari threading import failed: {e}")
    NAPARI_AVAILABLE = False
    print("✅ Napari Workers: Will skip napari-specific functionality")

if NAPARI_AVAILABLE:
    from .base_workers import AbstractThumbnailWorker

if TYPE_CHECKING:
    from copick.models import CopickRun


if NAPARI_AVAILABLE:
    class NapariWorkerSignals(QObject):
        """napari-specific worker signals."""
        
        thumbnail_loaded = Signal(str, object, object)  # thumbnail_id, pixmap, error


    class NapariThumbnailWorker(AbstractThumbnailWorker):
        """napari-specific thumbnail worker using @thread_worker decorator."""
        
        def __init__(
            self,
            run: "CopickRun",
            thumbnail_id: str,
            callback: Callable[[str, Optional[Any], Optional[str]], None],
            force_regenerate: bool = False
        ):
            super().__init__(run, thumbnail_id, callback, force_regenerate)
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
                    print(f"🔍 NapariWorker: Selecting best tomogram for '{self.thumbnail_id}'")
                    # Select best tomogram
                    tomogram = self._select_best_tomogram(self.run)
                    if not tomogram:
                        print(f"❌ NapariWorker: No tomogram found for '{self.thumbnail_id}'")
                        return None, "No tomogram found"
                        
                    print(f"🎨 NapariWorker: Generating thumbnail array for '{self.thumbnail_id}'")
                    # Generate thumbnail array
                    thumbnail_array = self._generate_thumbnail_array(tomogram)
                    if thumbnail_array is None:
                        print(f"❌ NapariWorker: Failed to generate thumbnail array for '{self.thumbnail_id}'")
                        return None, "Failed to generate thumbnail"
                        
                    print(f"🖼️ NapariWorker: Converting to pixmap for '{self.thumbnail_id}'")
                    # Convert to QPixmap
                    pixmap = self._array_to_pixmap(thumbnail_array)
                    if pixmap is None:
                        print(f"❌ NapariWorker: Failed to convert to pixmap for '{self.thumbnail_id}'")
                        return None, "Failed to convert to pixmap"
                        
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
            
        def _array_to_pixmap(self, array: Any) -> Optional[QPixmap]:
            """Convert numpy array to QPixmap."""
            if not NAPARI_AVAILABLE:
                return None
                
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


    class NapariWorkerManager:
        """Manages napari thumbnail workers."""
        
        def __init__(self):
            self._active_workers = []
            
        def start_thumbnail_worker(
            self,
            run: "CopickRun",
            thumbnail_id: str,
            callback: Callable[[str, Optional[Any], Optional[str]], None],
            force_regenerate: bool = False
        ) -> None:
            """Start a thumbnail loading worker."""
            worker = NapariThumbnailWorker(run, thumbnail_id, callback, force_regenerate)
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