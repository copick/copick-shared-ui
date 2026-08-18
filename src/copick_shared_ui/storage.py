"""Read-only storage helpers used by shared UI components."""

from typing import TYPE_CHECKING, Any

import zarr
from copick.util.ome import get_level_path, get_multiscales

if TYPE_CHECKING:
    from copick.models import CopickTomogram


def open_coarsest_tomogram_array(tomogram: "CopickTomogram") -> Any:
    """Open the final metadata-defined tomogram pyramid level without loading it.

    The ordered OME multiscale metadata is the sole authority for pyramid
    selection. Array labels and root iteration order are deliberately ignored.
    """
    group = zarr.open_group(store=tomogram.zarr(), mode="r")
    try:
        multiscales = get_multiscales(group)
    except KeyError as error:
        raise ValueError("OME-Zarr multiscales metadata not found") from error
    if not isinstance(multiscales, list) or not multiscales:
        raise ValueError("OME-Zarr multiscales metadata is empty")

    first_multiscale = multiscales[0]
    if not isinstance(first_multiscale, dict):
        raise ValueError("OME-Zarr first multiscale entry is malformed")

    datasets = first_multiscale.get("datasets")
    if not isinstance(datasets, list) or not datasets:
        raise ValueError("OME-Zarr first multiscale has no datasets")

    level = len(datasets) - 1
    try:
        dataset_path = get_level_path(group, level)
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError("OME-Zarr coarsest dataset path is missing") from error
    if not isinstance(dataset_path, str) or not dataset_path:
        raise ValueError("OME-Zarr coarsest dataset path is missing")

    try:
        array = group[dataset_path]
    except KeyError as error:
        raise ValueError(f"OME-Zarr dataset path {dataset_path!r} does not exist") from error

    if not isinstance(array, zarr.Array):
        raise TypeError(f"OME-Zarr dataset path {dataset_path!r} is not an array")
    if array.ndim != 3:
        raise ValueError(f"Tomogram dataset {dataset_path!r} must be three-dimensional, got {array.ndim} dimensions")

    return array
