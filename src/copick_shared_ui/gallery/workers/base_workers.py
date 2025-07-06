"""Abstract base classes for background thumbnail loading workers."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Callable, Optional

if TYPE_CHECKING:
    from copick.models import CopickRun, CopickTomogram


class AbstractThumbnailWorker(ABC):
    """Abstract base class for thumbnail loading workers."""

    def __init__(
        self,
        run: "CopickRun",
        thumbnail_id: str,
        callback: Callable[[str, Optional[Any], Optional[str]], None],
        force_regenerate: bool = False,
    ):
        self.run = run
        self.thumbnail_id = thumbnail_id
        self.callback = callback
        self.force_regenerate = force_regenerate

    @abstractmethod
    def start(self) -> None:
        """Start the thumbnail loading work."""
        pass

    @abstractmethod
    def cancel(self) -> None:
        """Cancel the thumbnail loading work."""
        pass

    def _select_best_tomogram(self, run: "CopickRun") -> Optional["CopickTomogram"]:
        """Select the best tomogram from a run (prefer denoised, highest voxel spacing)."""
        try:
            all_tomograms = []

            # Collect all tomograms from all voxel spacings
            for vs in run.voxel_spacings:
                for tomo in vs.tomograms:
                    all_tomograms.append(tomo)

            if not all_tomograms:
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
                            return tomo

                # If no preferred type found, return the first tomogram at this voxel spacing
                if vs_tomograms:
                    return vs_tomograms[0]

            # Fallback: return any tomogram
            return all_tomograms[0] if all_tomograms else None

        except Exception as e:
            print(f"Error selecting best tomogram: {e}")
            return None

    def _generate_thumbnail_array(self, tomogram: "CopickTomogram") -> Optional[Any]:
        """Generate thumbnail array from tomogram data."""
        try:
            import numpy as np
            import zarr

            print(f"🔧 Loading zarr data for tomogram: {tomogram.tomo_type}")

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
                    print(f"🔧 Using highest binning scale level {highest_scale} from multi-scale zarr for thumbnail")
                else:
                    # Fallback to first key
                    first_key = list(zarr_group.keys())[0]
                    tomo_data = zarr_group[first_key]
                    print(f"🔧 Using first key '{first_key}' from zarr group")
            else:
                # Direct zarr array
                tomo_data = zarr_group
                print("🔧 Using direct zarr array")

            print(f"📐 Tomogram shape: {tomo_data.shape}")

            # Calculate downsampling factor based on data size
            target_size = 200
            z_size, y_size, x_size = tomo_data.shape

            # Use middle slice for 2D thumbnail
            mid_z = z_size // 2
            print(f"📍 Using middle slice z={mid_z} of {z_size}")

            # Calculate downsampling for x and y dimensions
            downsample_x = max(1, x_size // target_size)
            downsample_y = max(1, y_size // target_size)
            print(f"📉 Downsampling: x={downsample_x}, y={downsample_y}")

            # Extract and downsample middle slice
            print("✂️ Extracting slice...")
            slice_data = tomo_data[mid_z, ::downsample_y, ::downsample_x]
            print(f"📊 Slice shape: {slice_data.shape}")

            # Convert to numpy array
            slice_array = np.array(slice_data)
            print(f"🔢 Array shape: {slice_array.shape}, dtype: {slice_array.dtype}")

            # Normalize to 0-255 range
            slice_array = slice_array.astype(np.float32)
            data_min, data_max = slice_array.min(), slice_array.max()
            print(f"📈 Data range: {data_min} to {data_max}")

            if data_max > data_min:
                slice_array = ((slice_array - data_min) / (data_max - data_min) * 255).astype(np.uint8)
            else:
                slice_array = np.zeros_like(slice_array, dtype=np.uint8)

            print(f"✅ Thumbnail array generated: shape={slice_array.shape}, dtype={slice_array.dtype}")
            return slice_array

        except Exception as e:
            print(f"Error generating thumbnail array: {e}")
            import traceback

            traceback.print_exc()
            return None
