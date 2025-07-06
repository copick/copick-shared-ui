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
    from .base_manager import AbstractWorkerManager
    from .data_worker import AbstractDataWorker

if TYPE_CHECKING:
    from copick.models import CopickRun, CopickTomogram


if NAPARI_AVAILABLE:

    class NapariWorkerSignals(QObject):
        """napari-specific worker signals."""

        thumbnail_loaded = Signal(str, object, object)  # thumbnail_id, pixmap, error
        data_loaded = Signal(str, object, object)  # data_type, data, error

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
            self._finished = False

        def start(self) -> None:
            """Start the thumbnail loading work using napari's thread_worker."""
            print(f"🚀 NapariWorker: Starting thumbnail work for '{self.thumbnail_id}'")

            if not NAPARI_AVAILABLE:
                print(f"❌ NapariWorker: napari not available for '{self.thumbnail_id}'")
                self.callback(self.thumbnail_id, None, "napari not available")
                return

            # Create the worker function as a generator for better control
            @thread_worker
            def load_thumbnail():
                print(f"🔧 NapariWorker: Inside generator thread_worker for '{self.thumbnail_id}'")

                # Check cancellation before starting
                if self._cancelled:
                    print(f"⚠️ NapariWorker: Cancelled '{self.thumbnail_id}' before starting")
                    return None, "Cancelled"

                try:
                    # Yield to allow interruption
                    yield "Starting thumbnail generation..."

                    # Check cancellation again
                    if self._cancelled:
                        print(f"⚠️ NapariWorker: Cancelled '{self.thumbnail_id}' during execution")
                        return None, "Cancelled"

                    # Break up the thumbnail generation to allow cancellation
                    # Step 1: Check cache
                    yield "Checking cache..."
                    if self._cancelled:
                        return None, "Cancelled"

                    # Check if we can use cached result
                    if self._cache and self._cache_key and not self.force_regenerate:
                        cached_pixmap = self._cache.load_thumbnail(self._cache_key)
                        if cached_pixmap is not None:
                            print(f"📦 Using cached thumbnail for '{self.thumbnail_id}'")
                            return cached_pixmap, None

                    # Step 2: Determine tomogram to use
                    yield "Selecting tomogram..."
                    if self._cancelled:
                        return None, "Cancelled"

                    if self._is_tomogram():
                        tomogram = self.item
                    else:
                        # Item is a run, select best tomogram
                        run = self.item
                        tomogram = self._select_best_tomogram(run)
                        if not tomogram:
                            return None, "No suitable tomogram found in run"

                    # Step 3: Generate thumbnail with periodic yielding
                    yield "Loading tomogram data..."
                    if self._cancelled:
                        return None, "Cancelled"

                    # Generate thumbnail array with cancellation checks
                    thumbnail_array = self._generate_thumbnail_array_with_cancellation(tomogram)
                    if thumbnail_array is None:
                        return None, "Failed to generate thumbnail array"

                    if self._cancelled:
                        return None, "Cancelled"

                    # Step 4: Convert to pixmap
                    yield "Converting to pixmap..."
                    if self._cancelled:
                        return None, "Cancelled"

                    pixmap = self._array_to_pixmap(thumbnail_array)
                    if pixmap is None:
                        return None, "Failed to convert array to pixmap"

                    # Step 5: Cache result
                    yield "Caching result..."
                    if self._cancelled:
                        return None, "Cancelled"

                    if self._cache and self._cache_key:
                        try:
                            success = self._cache.save_thumbnail(self._cache_key, pixmap)
                            if success:
                                print(f"💾 Cached thumbnail for '{self.thumbnail_id}'")
                        except Exception as e:
                            print(f"⚠️ Error caching thumbnail: {e}")

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
                # Use napari's quit method to abort the worker
                if hasattr(self._worker_func, "quit"):
                    print(f"🛑 NapariWorker: Calling quit() on worker for '{self.thumbnail_id}'")
                    self._worker_func.quit()
                else:
                    print(f"⚠️ NapariWorker: Worker for '{self.thumbnail_id}' has no quit method")

        def _on_worker_finished(self, result):
            """Handle worker completion."""
            self._finished = True
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

        def _generate_thumbnail_array_with_cancellation(self, tomogram: "CopickTomogram") -> Optional[Any]:
            """Generate thumbnail array from tomogram data with cancellation checks."""
            try:
                import numpy as np
                import zarr

                print(f"🔧 Loading zarr data for tomogram: {tomogram.tomo_type}")

                # Check cancellation before heavy I/O
                if self._cancelled:
                    return None

                # Load tomogram data - handle multi-scale zarr properly
                zarr_group = zarr.open(tomogram.zarr(), mode="r")

                # Check cancellation after opening zarr
                if self._cancelled:
                    return None

                # Get the data array - handle multi-scale structure
                if hasattr(zarr_group, "keys") and callable(zarr_group.keys):
                    # Multi-scale zarr group - get the HIGHEST binning level for faster thumbnails
                    scale_levels = sorted([k for k in zarr_group.keys() if k.isdigit()], key=int)  # noqa: SIM118
                    if scale_levels:
                        # Use the highest scale level (most binned/smallest) for thumbnails
                        highest_scale = scale_levels[-1]  # Last element is highest number = most binned
                        tomo_data = zarr_group[highest_scale]
                        print(
                            f"🔧 Using highest binning scale level {highest_scale} from multi-scale zarr for thumbnail",
                        )
                    else:
                        # Fallback to first key
                        first_key = list(zarr_group.keys())[0]
                        tomo_data = zarr_group[first_key]
                        print(f"🔧 Using first key '{first_key}' from zarr group")
                else:
                    # Direct zarr array
                    tomo_data = zarr_group
                    print("🔧 Using direct zarr array")

                # Check cancellation after getting data reference
                if self._cancelled:
                    return None

                print(f"📐 Tomogram shape: {tomo_data.shape}")

                # Calculate downsampling factor based on data size
                target_size = 200
                z_size, y_size, x_size = tomo_data.shape

                # Use middle slice for 2D thumbnail
                mid_z = z_size // 2

                # Check cancellation before reading slice data
                if self._cancelled:
                    return None

                # Read the middle slice data
                mid_slice = tomo_data[mid_z]

                # Check cancellation after reading slice
                if self._cancelled:
                    return None

                # Calculate downsampling for the slice
                downsample_y = max(1, y_size // target_size)
                downsample_x = max(1, x_size // target_size)

                # Downsample the slice
                thumbnail = mid_slice[::downsample_y, ::downsample_x]

                # Check cancellation after downsampling
                if self._cancelled:
                    return None

                # Normalize to 0-255 range
                thumb_min, thumb_max = thumbnail.min(), thumbnail.max()
                if thumb_max > thumb_min:
                    thumbnail = ((thumbnail - thumb_min) / (thumb_max - thumb_min) * 255).astype(np.uint8)
                else:
                    thumbnail = np.zeros_like(thumbnail, dtype=np.uint8)

                print(f"📐 Generated thumbnail shape: {thumbnail.shape}")
                return thumbnail

            except Exception as e:
                if self._cancelled:
                    return None
                print(f"Error generating thumbnail array: {e}")
                return None

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

    class NapariDataWorker(AbstractDataWorker):
        """napari-specific data worker using @thread_worker decorator."""

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
            """Start the data loading work using napari's thread_worker."""
            print(f"🚀 NapariDataWorker: Starting data loading for '{self.data_type}'")

            if not NAPARI_AVAILABLE:
                print(f"❌ NapariDataWorker: napari not available for '{self.data_type}'")
                self.callback(self.data_type, None, "napari not available")
                return

            # Capture variables for the worker function
            worker_run = self.run
            worker_data_type = self.data_type
            worker_cancelled = lambda: self._cancelled  # noqa: E731

            # Create the worker function as a generator for better control
            @thread_worker
            def load_data():
                print(f"🔧 NapariDataWorker: Inside generator thread_worker for '{worker_data_type}'")

                if worker_cancelled():
                    print(f"⚠️ NapariDataWorker: Cancelled '{worker_data_type}' before starting")
                    return None, "Cancelled"

                try:
                    # Yield to allow interruption
                    yield f"Starting {worker_data_type} loading..."

                    # Check cancellation again
                    if worker_cancelled():
                        print(f"⚠️ NapariDataWorker: Cancelled '{worker_data_type}' during execution")
                        return None, "Cancelled"

                    # Use base class data loading logic directly
                    print(f"🔍 Loading {worker_data_type} for run '{worker_run.name}'")

                    if worker_data_type == "voxel_spacings":
                        data = list(worker_run.voxel_spacings)
                    elif worker_data_type == "tomograms":
                        tomograms = []
                        for vs in worker_run.voxel_spacings:
                            if worker_cancelled():
                                return None, "Cancelled"
                            tomograms.extend(list(vs.tomograms))
                        data = tomograms
                    elif worker_data_type == "picks":
                        data = list(worker_run.picks)
                    elif worker_data_type == "meshes":
                        data = list(worker_run.meshes)
                    elif worker_data_type == "segmentations":
                        data = list(worker_run.segmentations)
                    else:
                        return None, f"Unknown data type: {worker_data_type}"

                    if worker_cancelled():
                        return None, "Cancelled"

                    print(f"✅ NapariDataWorker: Successfully loaded {len(data)} {worker_data_type} items")
                    return data, None

                except Exception as e:
                    print(f"💥 NapariDataWorker: Exception loading '{worker_data_type}': {e}")
                    import traceback

                    traceback.print_exc()
                    return None, str(e)

            # Connect worker signals
            print(f"🔗 NapariDataWorker: Creating and connecting worker for '{self.data_type}'")
            worker = load_data()
            worker.returned.connect(self._on_worker_finished)
            worker.errored.connect(self._on_worker_error)

            # Store reference to worker
            self._worker_func = worker
            print(f"📦 NapariDataWorker: Worker stored for '{self.data_type}'")

            # Actually start the worker!
            print(f"▶️ NapariDataWorker: Starting worker execution for '{self.data_type}'")
            worker.start()

        def cancel(self) -> None:
            """Cancel the data loading work."""
            self._cancelled = True
            if self._worker_func:
                # Use napari's quit method to abort the worker
                if hasattr(self._worker_func, "quit"):
                    print(f"🛑 NapariDataWorker: Calling quit() on worker for '{self.data_type}'")
                    self._worker_func.quit()
                else:
                    print(f"⚠️ NapariDataWorker: Worker for '{self.data_type}' has no quit method")

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

    class NapariWorkerManager(AbstractWorkerManager):
        """Manages napari thumbnail and data workers with thread limiting."""

        def __init__(self, max_concurrent_workers: int = 8):
            """Initialize napari worker manager.

            Args:
                max_concurrent_workers: Maximum number of workers that can run simultaneously.
                    Default is 8 to balance performance and system stability with large projects.
            """
            super().__init__(max_concurrent_workers)

        def _create_thumbnail_worker(
            self,
            item: Union["CopickRun", "CopickTomogram"],
            thumbnail_id: str,
            callback: Callable[[str, Optional[Any], Optional[str]], None],
            force_regenerate: bool = False,
        ) -> NapariThumbnailWorker:
            """Create a napari thumbnail worker."""
            return NapariThumbnailWorker(item, thumbnail_id, callback, force_regenerate)

        def _create_data_worker(
            self,
            run: "CopickRun",
            data_type: str,
            callback: Callable[[str, Optional[Any], Optional[str]], None],
        ) -> NapariDataWorker:
            """Create a napari data worker."""
            return NapariDataWorker(run, data_type, callback)

        def _start_worker(self, worker: Union[NapariThumbnailWorker, NapariDataWorker]) -> None:
            """Start a napari worker."""
            worker.start()

        def _is_worker_active(self, worker: Union[NapariThumbnailWorker, NapariDataWorker]) -> bool:
            """Check if a napari worker is still active."""
            return (
                hasattr(worker, "_worker_func")
                and worker._worker_func is not None
                and hasattr(worker, "_finished")
                and not worker._finished
            )

        def _cancel_worker(self, worker: Union[NapariThumbnailWorker, NapariDataWorker]) -> None:
            """Cancel a napari worker."""
            worker.cancel()
