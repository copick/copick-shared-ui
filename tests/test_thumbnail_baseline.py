"""Executable baseline for the storage-sensitive thumbnail behavior."""

import numpy as np

from tests.helpers import ArrayThumbnailWorker, gradient_volume, write_ome_zarr_04


def _normalized_middle_slice(volume: np.ndarray) -> np.ndarray:
    values = volume[volume.shape[0] // 2].astype(np.float32)
    return ((values - values.min()) / (values.max() - values.min()) * 255).astype(np.uint8)


def test_numeric_pyramid_uses_current_coarsest_level(tmp_path):
    fine = gradient_volume(1000)
    coarse = gradient_volume()
    tomogram = write_ome_zarr_04(tmp_path / "numeric.zarr", {"0": fine, "1": coarse}, ["0", "1"])

    result = ArrayThumbnailWorker(tomogram)._generate_thumbnail_array(tomogram)

    np.testing.assert_array_equal(result, _normalized_middle_slice(coarse))


def test_constant_middle_slice_normalizes_to_zero(tmp_path):
    constant = np.full((3, 6, 8), 7, dtype=np.float32)
    tomogram = write_ome_zarr_04(tmp_path / "constant.zarr", {"0": constant}, ["0"])

    result = ArrayThumbnailWorker(tomogram)._generate_thumbnail_array(tomogram)

    np.testing.assert_array_equal(result, np.zeros((6, 8), dtype=np.uint8))


def test_metadata_path_wins_over_numeric_distractor(tmp_path):
    distractor = np.zeros((3, 6, 8), dtype=np.float32)
    declared = gradient_volume()
    tomogram = write_ome_zarr_04(
        tmp_path / "distractor.zarr",
        {"0": distractor, "s0": declared},
        ["s0"],
    )

    result = ArrayThumbnailWorker(tomogram)._generate_thumbnail_array(tomogram)

    np.testing.assert_array_equal(result, _normalized_middle_slice(declared))


def test_public_pixmap_contract_returns_array_and_no_error(tmp_path):
    values = gradient_volume()
    tomogram = write_ome_zarr_04(tmp_path / "public.zarr", {"0": values}, ["0"])

    pixmap, error = ArrayThumbnailWorker(tomogram).generate_thumbnail_pixmap()

    np.testing.assert_array_equal(pixmap, _normalized_middle_slice(values))
    assert error is None
