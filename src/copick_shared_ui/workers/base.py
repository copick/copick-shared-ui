"""Abstract base classes for background thumbnail loading workers with unified caching."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Callable, Optional, Union

if TYPE_CHECKING:
    from copick.models import CopickRun, CopickTomogram


class AbstractThumbnailWorker(ABC):
    """Abstract base class for thumbnail loading workers with unified caching support."""

    # Class-level cache for best tomogram selections to avoid recomputation
    _best_tomogram_cache = {}

    def __init__(
        self,
        item: Union["CopickRun", "CopickTomogram"],
        thumbnail_id: str,
        callback: Callable[[str, Optional[Any], Optional[str]], None],
        force_regenerate: bool = False,
    ):
        self.item = item
        self.thumbnail_id = thumbnail_id
        self.callback = callback
        self.force_regenerate = force_regenerate

        # Set up caching
        self._cache = None
        self._cache_key = None
        self._setup_cache()

    def _setup_cache(self) -> None:
        """Set up thumbnail cache for this worker."""
        try:
            from ..core.thumbnail_cache import get_global_cache

            self._cache = get_global_cache()

            # Create cache key based on item type
            if self._is_tomogram():
                tomogram = self.item
                run_name = tomogram.voxel_spacing.run.name
                self._cache_key = self._cache.get_cache_key(
                    run_name=run_name,
                    tomogram_type=tomogram.tomo_type,
                    voxel_spacing=tomogram.voxel_spacing.voxel_size,
                )
            else:
                # For runs, we'll create cache key once we know the best tomogram
                run = self.item
                self._cache_key = self._cache.get_cache_key(run_name=run.name)

        except Exception as e:
            print(f"Warning: Could not set up thumbnail cache: {e}")
            self._cache = None
            self._cache_key = None

    def _is_tomogram(self) -> bool:
        """Check if the item is a tomogram (vs a run)."""
        return hasattr(self.item, "tomo_type")

    @abstractmethod
    def start(self) -> None:
        """Start the thumbnail loading work."""
        pass

    @abstractmethod
    def cancel(self) -> None:
        """Cancel the thumbnail loading work."""
        pass

    def _select_best_tomogram(self, run: "CopickRun") -> Optional["CopickTomogram"]:
        """Select the best tomogram from a run with caching (prefer denoised, highest voxel spacing)."""
        # Check cache first
        cache_key = f"{run.name}_best_tomogram"
        if cache_key in self._best_tomogram_cache:
            cached_result = self._best_tomogram_cache[cache_key]
            if cached_result is not None:
                return cached_result

        try:
            all_tomograms = []

            # Collect all tomograms from all voxel spacings
            for vs in run.voxel_spacings:
                for tomo in vs.tomograms:
                    all_tomograms.append(tomo)

            if not all_tomograms:
                self._best_tomogram_cache[cache_key] = None
                return None

            # Preference order for tomogram types (denoised first)
            preferred_types = ["denoised", "wbp"]

            # Group by voxel spacing (highest first)
            voxel_spacings = sorted({tomo.voxel_spacing.voxel_size for tomo in all_tomograms}, reverse=True)

            # Try each voxel spacing, starting with highest
            for vs_size in voxel_spacings:
                vs_tomograms = [tomo for tomo in all_tomograms if tomo.voxel_spacing.voxel_size == vs_size]

                # Try preferred types in order
                for preferred_type in preferred_types:
                    for tomo in vs_tomograms:
                        if preferred_type.lower() in tomo.tomo_type.lower():
                            self._best_tomogram_cache[cache_key] = tomo
                            return tomo

                # If no preferred type found, return the first tomogram at this voxel spacing
                if vs_tomograms:
                    selected = vs_tomograms[0]
                    self._best_tomogram_cache[cache_key] = selected
                    return selected

            # Final fallback: return any tomogram
            if all_tomograms:
                selected = all_tomograms[0]
                self._best_tomogram_cache[cache_key] = selected
                return selected

            self._best_tomogram_cache[cache_key] = None
            return None

        except Exception as e:
            print(f"Error selecting best tomogram: {e}")
            self._best_tomogram_cache[cache_key] = None
            return None

    def generate_thumbnail_pixmap(self) -> tuple[Optional[Any], Optional[str]]:
        """Generate thumbnail pixmap from the item (run or tomogram). Returns (pixmap, error)."""
        # Check cache first (if not force regenerating)
        if not self.force_regenerate and self._cache and self._cache_key and self._cache.has_thumbnail(self._cache_key):
            cached_pixmap = self._cache.load_thumbnail(self._cache_key)
            if cached_pixmap is not None:
                return cached_pixmap, None

        # Determine the tomogram to use
        if self._is_tomogram():
            tomogram = self.item
            # Update cache key with specific tomogram info
            if self._cache:
                run_name = tomogram.voxel_spacing.run.name
                self._cache_key = self._cache.get_cache_key(
                    run_name=run_name,
                    tomogram_type=tomogram.tomo_type,
                    voxel_spacing=tomogram.voxel_spacing.voxel_size,
                )
        else:
            # Item is a run, select best tomogram
            run = self.item
            tomogram = self._select_best_tomogram(run)
            if not tomogram:
                return None, "No suitable tomogram found in run"

            # Update cache key with selected tomogram info
            if self._cache:
                self._cache_key = self._cache.get_cache_key(
                    run_name=run.name,
                    tomogram_type=tomogram.tomo_type,
                    voxel_spacing=tomogram.voxel_spacing.voxel_size,
                )

        # Generate thumbnail array
        thumbnail_array = self._generate_thumbnail_array(tomogram)
        if thumbnail_array is None:
            return None, "Failed to generate thumbnail array"

        # Convert to pixmap
        pixmap = self._array_to_pixmap(thumbnail_array)
        if pixmap is None:
            return None, "Failed to convert array to pixmap"

        # Cache the result
        if self._cache and self._cache_key:
            try:
                _ = self._cache.save_thumbnail(self._cache_key, pixmap)
            except Exception as e:
                print(f"⚠️ Error caching thumbnail: {e}")

        return pixmap, None

    @abstractmethod
    def _array_to_pixmap(self, array: Any) -> Optional[Any]:
        """Convert numpy array to platform-specific pixmap."""
        pass

    def _generate_thumbnail_array(self, tomogram: "CopickTomogram") -> Optional[Any]:
        """Generate thumbnail array from tomogram data."""
        try:
            import numpy as np
            import zarr

            # Load tomogram data - handle multi-scale zarr properly
            zarr_group = zarr.open(tomogram.zarr(), mode="r")

            # Get the data array - handle multi-scale structure
            if hasattr(zarr_group, "keys") and callable(zarr_group.keys):
                # Multi-scale zarr group - get the HIGHEST binning level for faster thumbnails
                scale_levels = sorted([k for k in zarr_group.keys() if k.isdigit()], key=int)  # noqa: SIM118
                if scale_levels:
                    # Use the highest scale level (most binned/smallest) for thumbnails
                    highest_scale = scale_levels[-1]  # Last element is highest number = most binned
                    tomo_data = zarr_group[highest_scale]
                else:
                    # Fallback to first key
                    first_key = list(zarr_group.keys())[0]
                    tomo_data = zarr_group[first_key]
            else:
                # Direct zarr array
                tomo_data = zarr_group

            # Calculate downsampling factor based on data size
            target_size = 200
            z_size, y_size, x_size = tomo_data.shape

            # Use middle slice for 2D thumbnail
            mid_z = z_size // 2

            # Calculate downsampling for x and y dimensions
            downsample_x = max(1, x_size // target_size)
            downsample_y = max(1, y_size // target_size)

            # Extract and downsample middle slice
            slice_data = tomo_data[mid_z, ::downsample_y, ::downsample_x]

            # Convert to numpy array
            slice_array = np.array(slice_data)

            # Normalize to 0-255 range
            slice_array = slice_array.astype(np.float32)
            data_min, data_max = slice_array.min(), slice_array.max()

            if data_max > data_min:
                slice_array = ((slice_array - data_min) / (data_max - data_min) * 255).astype(np.uint8)
            else:
                slice_array = np.zeros_like(slice_array, dtype=np.uint8)

            return slice_array

        except Exception as e:
            print(f"Error generating thumbnail array: {e}")
            import traceback

            traceback.print_exc()
            return None
