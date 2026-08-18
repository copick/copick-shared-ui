"""Tests for metadata-defined, layout-agnostic tomogram reads."""

import hashlib
from pathlib import Path

import numpy as np
import pytest
import zarr

from copick_shared_ui.storage import open_coarsest_tomogram_array
from tests.helpers import DummyTomogram, gradient_volume, write_ome_zarr


def _snapshot(path: Path) -> dict[str, str]:
    return {
        str(item.relative_to(path)): hashlib.sha256(item.read_bytes()).hexdigest()
        for item in sorted(path.rglob("*"))
        if item.is_file()
    }


@pytest.mark.parametrize(
    ("ome_version", "zarr_format", "paths"),
    [
        ("0.4", 2, ["0", "1"]),
        ("0.4", 2, ["s0", "s1"]),
        ("0.5", 3, ["0", "1"]),
        ("0.5", 3, ["fine", "coarse"]),
    ],
)
def test_coarsest_array_follows_ordered_metadata(tmp_path, ome_version, zarr_format, paths):
    fine = gradient_volume(1000)
    coarse = gradient_volume()
    store_path = tmp_path / f"ome-{ome_version}-zarr-{zarr_format}.zarr"
    tomogram = write_ome_zarr(
        store_path,
        {paths[0]: fine, paths[1]: coarse},
        paths,
        ome_version=ome_version,
        zarr_format=zarr_format,
        chunks=(1, 3, 4),
    )
    before = _snapshot(store_path)

    array = open_coarsest_tomogram_array(tomogram)

    assert array.path == paths[-1]
    np.testing.assert_array_equal(array[:], coarse)
    assert _snapshot(store_path) == before


@pytest.mark.parametrize(
    ("chunks", "shards", "chunk_key_encoding"),
    [
        ((1, 3, 4), None, None),
        ((1, 3, 4), (3, 6, 8), {"name": "v2", "configuration": {"separator": "."}}),
        ((1, 3, 4), (2, 3, 4), None),
        ((1, 2, 2), None, {"name": "v2", "configuration": {"separator": "."}}),
    ],
)
def test_reader_ignores_valid_zarr_v3_layout_choices(tmp_path, chunks, shards, chunk_key_encoding):
    values = gradient_volume()
    tomogram = write_ome_zarr(
        tmp_path / "layout.zarr",
        {"arbitrary-level": values},
        ["arbitrary-level"],
        ome_version="0.5",
        zarr_format=3,
        chunks=chunks,
        shards=shards,
        chunk_key_encoding=chunk_key_encoding,
    )

    array = open_coarsest_tomogram_array(tomogram)

    np.testing.assert_array_equal(array[1, ::2, ::3], values[1, ::2, ::3])


@pytest.mark.parametrize(
    ("metadata", "message"),
    [
        ({"ome": {"version": "0.5", "multiscales": []}}, "multiscales metadata is empty"),
        (
            {"ome": {"version": "0.5", "multiscales": [{}]}},
            "first multiscale has no datasets",
        ),
        (
            {"ome": {"version": "0.5", "multiscales": [{"datasets": []}]}},
            "first multiscale has no datasets",
        ),
        (
            {"ome": {"version": "0.5", "multiscales": [{"datasets": [{}]}]}},
            "coarsest dataset path is missing",
        ),
    ],
)
def test_empty_or_malformed_metadata_fails_clearly(tmp_path, metadata, message):
    store_path = tmp_path / "invalid.zarr"
    group = zarr.open_group(store=str(store_path), mode="w", zarr_format=3)
    group.attrs.update(metadata)
    before = _snapshot(store_path)

    with pytest.raises(ValueError, match=message):
        open_coarsest_tomogram_array(DummyTomogram(str(store_path)))

    assert _snapshot(store_path) == before


def test_missing_metadata_fails_without_mutating_store(tmp_path):
    store_path = tmp_path / "missing-metadata.zarr"
    zarr.open_group(store=str(store_path), mode="w", zarr_format=3)
    before = _snapshot(store_path)

    with pytest.raises(ValueError, match="multiscales metadata not found"):
        open_coarsest_tomogram_array(DummyTomogram(str(store_path)))

    assert _snapshot(store_path) == before


def test_missing_declared_path_fails_clearly(tmp_path):
    tomogram = write_ome_zarr(
        tmp_path / "missing-path.zarr",
        {"fine": gradient_volume()},
        ["fine", "absent"],
        ome_version="0.5",
        zarr_format=3,
    )

    with pytest.raises(ValueError, match="dataset path 'absent' does not exist"):
        open_coarsest_tomogram_array(tomogram)


def test_non_three_dimensional_dataset_is_rejected(tmp_path):
    tomogram = write_ome_zarr(
        tmp_path / "two-dimensional.zarr",
        {"preview": np.ones((6, 8), dtype=np.float32)},
        ["preview"],
        ome_version="0.5",
        zarr_format=3,
    )

    with pytest.raises(ValueError, match="must be three-dimensional"):
        open_coarsest_tomogram_array(tomogram)


def test_empty_store_open_is_read_only(tmp_path):
    store_path = tmp_path / "empty.zarr"
    store_path.mkdir()

    with pytest.raises(zarr.errors.GroupNotFoundError, match="No group found"):
        open_coarsest_tomogram_array(DummyTomogram(str(store_path)))

    assert list(store_path.iterdir()) == []


def test_root_array_is_not_accepted_as_a_tomogram_group(tmp_path):
    store_path = tmp_path / "root-array.zarr"
    zarr.open_array(store=str(store_path), mode="w", shape=(3, 6, 8), dtype="f4", zarr_format=3)
    before = _snapshot(store_path)

    with pytest.raises(zarr.errors.ContainsArrayError, match="array already exists"):
        open_coarsest_tomogram_array(DummyTomogram(str(store_path)))

    assert _snapshot(store_path) == before
