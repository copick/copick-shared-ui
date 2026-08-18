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


def write_ome_zarr(
    path: Path,
    datasets: dict[str, np.ndarray],
    declared_paths: list[str],
    *,
    ome_version: str,
    zarr_format: int,
    chunks: tuple[int, ...] | None = None,
    shards: tuple[int, ...] | None = None,
    chunk_key_encoding: dict[str, Any] | None = None,
) -> DummyTomogram:
    """Build a format-specific OME-Zarr fixture without production helpers."""
    group = zarr.open_group(store=str(path), mode="w", zarr_format=zarr_format)
    for name, values in datasets.items():
        options = {"chunks": chunks or tuple(max(1, size // 2) for size in values.shape)}
        if shards is not None:
            options["shards"] = shards
        if chunk_key_encoding is not None:
            options["chunk_key_encoding"] = chunk_key_encoding
        group.create_array(name, data=values, **options)

    multiscales = [
        {
            "version": ome_version,
            "axes": [
                {"name": "z", "type": "space"},
                {"name": "y", "type": "space"},
                {"name": "x", "type": "space"},
            ],
            "datasets": [{"path": dataset_path} for dataset_path in declared_paths],
        },
    ]
    if ome_version == "0.4":
        group.attrs["multiscales"] = multiscales
    elif ome_version == "0.5":
        group.attrs["ome"] = {"version": "0.5", "multiscales": multiscales}
    else:
        raise ValueError(f"Unsupported fixture OME-Zarr version: {ome_version}")

    return DummyTomogram(str(path))


def write_ome_zarr_04(path: Path, datasets: dict[str, np.ndarray], declared_paths: list[str]) -> DummyTomogram:
    """Build an OME-Zarr 0.4 / Zarr v2 fixture."""
    return write_ome_zarr(
        path,
        datasets,
        declared_paths,
        ome_version="0.4",
        zarr_format=2,
        chunks=(1, 3, 4),
    )
