"""Independent fixtures for thumbnail tests."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import zarr

from copick_shared_ui.workers.base import AbstractThumbnailWorker


@dataclass
class DummyRun:
    name: str = "run-1"


@dataclass
class DummyVoxelSpacing:
    run: DummyRun
    voxel_size: float = 10.0


class DummyTomogram:
    """Small tomogram-shaped object exposing the public storage contract."""

    def __init__(self, store: Any, tomo_type: str = "wbp", voxel_size: float = 10.0):
        self._store = store
        self.tomo_type = tomo_type
        self.voxel_spacing = DummyVoxelSpacing(DummyRun(), voxel_size)

    def zarr(self) -> Any:
        return self._store


class ArrayThumbnailWorker(AbstractThumbnailWorker):
    """Concrete worker that returns the normalized array instead of a Qt pixmap."""

    def __init__(self, item: DummyTomogram, *, force_regenerate: bool = True):
        super().__init__(item, "thumbnail", lambda *_args: None, force_regenerate)
        self._cache = None
        self._cache_key = None

    def start(self) -> None:
        pass

    def cancel(self) -> None:
        pass

    def _array_to_pixmap(self, array: Any) -> Any:
        return array


def gradient_volume(offset: int = 0) -> np.ndarray:
    """Return a nonconstant 3-D volume with a deterministic middle slice."""
    return np.arange(offset, offset + 3 * 6 * 8, dtype=np.float32).reshape(3, 6, 8)


def write_ome_zarr_04(path: Path, datasets: dict[str, np.ndarray], declared_paths: list[str]) -> DummyTomogram:
    """Build an OME-Zarr 0.4 / Zarr v2 fixture without using production helpers."""
    group = zarr.open_group(str(path), mode="w")
    for name, values in datasets.items():
        group.create_dataset(name, data=values, chunks=(1, 3, 4))
    group.attrs["multiscales"] = [
        {
            "version": "0.4",
            "axes": [
                {"name": "z", "type": "space"},
                {"name": "y", "type": "space"},
                {"name": "x", "type": "space"},
            ],
            "datasets": [{"path": dataset_path} for dataset_path in declared_paths],
        },
    ]
    return DummyTomogram(str(path))
