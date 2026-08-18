"""Tests for thumbnail materialization and public error contracts."""

import numpy as np
import zarr

from copick_shared_ui.workers.base import AbstractThumbnailWorker
from tests.helpers import ArrayThumbnailWorker, DummyTomogram


def test_public_synchronous_contract_returns_precise_storage_error(tmp_path):
    store_path = tmp_path / "missing-metadata.zarr"
    zarr.open_group(store=str(store_path), mode="w", zarr_format=3)
    worker = ArrayThumbnailWorker(DummyTomogram(str(store_path)))

    pixmap, error = worker.generate_thumbnail_pixmap()

    assert pixmap is None
    assert error == "OME-Zarr multiscales metadata not found"


def test_thumbnail_materializes_only_the_strided_middle_slice(monkeypatch):
    requests = []

    class LazyArray:
        shape = (5, 600, 400)

        def __getitem__(self, selection):
            requests.append(selection)
            return np.arange(200 * 200, dtype=np.float32).reshape(200, 200)

    monkeypatch.setattr("copick_shared_ui.storage.open_coarsest_tomogram_array", lambda _tomogram: LazyArray())
    worker = ArrayThumbnailWorker(DummyTomogram("unused"))

    result = worker._generate_thumbnail_array(worker.item)

    assert requests == [(2, slice(None, None, 3), slice(None, None, 2))]
    assert result.shape == (200, 200)
    assert result.dtype == np.uint8


def test_private_thumbnail_layer_does_not_swallow_storage_errors(monkeypatch):
    def fail(_tomogram):
        raise PermissionError("backend denied thumbnail read")

    monkeypatch.setattr("copick_shared_ui.storage.open_coarsest_tomogram_array", fail)
    worker = ArrayThumbnailWorker(DummyTomogram("unused"))

    try:
        worker._generate_thumbnail_array(worker.item)
    except PermissionError as error:
        assert str(error) == "backend denied thumbnail read"
    else:
        raise AssertionError("private thumbnail layer swallowed a storage error")


def test_public_thumbnail_layer_preserves_return_shape(monkeypatch):
    def fail(self, _tomogram):
        raise PermissionError("backend denied thumbnail read")

    monkeypatch.setattr(AbstractThumbnailWorker, "_generate_thumbnail_array", fail)
    worker = ArrayThumbnailWorker(DummyTomogram("unused"))

    assert worker.generate_thumbnail_pixmap() == (None, "backend denied thumbnail read")
