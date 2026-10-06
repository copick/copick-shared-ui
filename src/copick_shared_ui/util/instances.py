"""Instance IDs shared by picks, filaments and instance or panoptic segmentations: colours, ID sets, label statistics
and in-place label edits. Qt-free (numpy; scipy only where noted, imported lazily).

Colours follow one rule everywhere (napari, ChimeraX and copick-web): instance ``i > 0`` gets the HSV colour
``((i * 0.618033988749895) % 1, 0.65, 0.95)``; instance 0 (unassigned) keeps the object's colour.
"""

import colorsys
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

import numpy as np

GOLDEN_RATIO_CONJUGATE = 0.618033988749895
INSTANCE_SATURATION = 0.65
INSTANCE_VALUE = 0.95


def instance_rgb(instance_id: int) -> Tuple[float, float, float]:
    """The RGB colour (floats 0-1) of one instance ID (> 0)."""
    return colorsys.hsv_to_rgb((int(instance_id) * GOLDEN_RATIO_CONJUGATE) % 1.0, INSTANCE_SATURATION, INSTANCE_VALUE)


def instance_colors(
    instance_ids: Sequence[int],
    base_rgba: Sequence[float],
    dtype=float,
) -> np.ndarray:
    """One RGBA colour per entry of ``instance_ids``.

    Args:
        instance_ids: Instance ID per item (0 = unassigned).
        base_rgba: Colour of unassigned items, and the alpha of all items; floats 0-1 for ``dtype=float``, 0-255 for
            ``dtype=np.uint8``.
        dtype: ``float`` (0-1) or ``np.uint8`` (0-255).

    Returns:
        (N, 4) array.
    """
    ids = np.asarray(instance_ids, dtype=np.int64).reshape(-1)
    scale = 255.0 if np.dtype(dtype) == np.uint8 else 1.0
    colors = np.tile(np.asarray(base_rgba, dtype=float)[:4], (len(ids), 1))
    for value in np.unique(ids[ids > 0]):
        colors[ids == value, :3] = np.asarray(instance_rgb(value)) * scale
    if np.dtype(dtype) == np.uint8:
        return np.round(colors).astype(np.uint8)
    return colors


def instance_color_dict(
    instance_ids: Iterable[int],
    alpha: float = 1.0,
    hidden: Iterable[int] = (),
) -> Dict[int, Tuple[float, float, float, float]]:
    """``{id: (r, g, b, a)}`` (floats 0-1) for the given IDs; 0 and ``hidden`` IDs are transparent."""
    hidden = {int(h) for h in hidden}
    out = {0: (0.0, 0.0, 0.0, 0.0)}
    for i in instance_ids:
        i = int(i)
        if i <= 0:
            continue
        out[i] = (0.0, 0.0, 0.0, 0.0) if i in hidden else (*instance_rgb(i), float(alpha))
    return out


def instance_color_table(max_id: int, alpha: int = 255, hidden: Iterable[int] = ()) -> np.ndarray:
    """(max_id + 1, 4) uint8 lookup table indexed by instance ID; ID 0 and ``hidden`` IDs are transparent."""
    table = np.zeros((int(max_id) + 1, 4), dtype=np.uint8)
    if max_id > 0:
        ids = np.arange(1, int(max_id) + 1)
        hues = (ids * GOLDEN_RATIO_CONJUGATE) % 1.0
        rgb = np.array([colorsys.hsv_to_rgb(h, INSTANCE_SATURATION, INSTANCE_VALUE) for h in hues])
        table[1:, :3] = np.round(rgb * 255).astype(np.uint8)
        table[1:, 3] = alpha
    for h in hidden:
        if 0 < int(h) <= max_id:
            table[int(h)] = 0
    return table


def next_instance_id(*id_collections: Iterable[int]) -> int:
    """One more than the largest ID in any of the collections (arrays, lists, sets); at least 1."""
    best = 0
    for ids in id_collections:
        if ids is None:
            continue
        arr = ids if isinstance(ids, np.ndarray) else np.asarray(list(ids))
        if arr.size:
            best = max(best, int(arr.max()))
    return best + 1


_RANGE = re.compile(r"^\s*(\d+)\s*(?:-\s*(\d+))?\s*$")


def parse_id_set(text: str) -> Set[int]:
    """Parse ``"1-5, 9, 12"`` into ``{1, 2, 3, 4, 5, 9, 12}``.

    Raises:
        ValueError: If a part is neither a number nor a range.
    """
    ids: Set[int] = set()
    normalized = re.sub(r"\s*-\s*", "-", text or "")
    for part in filter(None, re.split(r"[,\s;]+", normalized)):
        m = _RANGE.match(part)
        if not m:
            raise ValueError(f"Not an ID or range: {part!r}")
        lo = int(m.group(1))
        hi = int(m.group(2)) if m.group(2) else lo
        if hi < lo:
            lo, hi = hi, lo
        ids.update(range(lo, hi + 1))
    return ids


def format_id_set(ids: Iterable[int]) -> str:
    """Format IDs compactly: ``{1, 2, 3, 5}`` -> ``"1-3, 5"``."""
    values = sorted({int(i) for i in ids})
    parts: List[str] = []
    i = 0
    while i < len(values):
        j = i
        while j + 1 < len(values) and values[j + 1] == values[j] + 1:
            j += 1
        parts.append(str(values[i]) if i == j else f"{values[i]}-{values[j]}")
        i = j + 1
    return ", ".join(parts)


def label_counts(volume: np.ndarray) -> Dict[int, int]:
    """Voxel count per non-zero label."""
    flat = np.asarray(volume).ravel()
    if flat.size == 0:
        return {}
    if flat.dtype.kind in "ui" and flat.dtype.itemsize <= 2 and flat.min() >= 0:
        counts = np.bincount(flat.astype(np.int64, copy=False))
        ids = np.nonzero(counts)[0]
        return {int(i): int(counts[i]) for i in ids if i != 0}
    ids, counts = np.unique(flat, return_counts=True)
    return {int(i): int(c) for i, c in zip(ids, counts) if i != 0}


def label_bboxes(volume: np.ndarray) -> Dict[int, Tuple[slice, slice, slice]]:
    """Bounding box (tuple of slices, in array axis order) per non-zero label (uses scipy)."""
    volume = np.asarray(volume)
    if volume.size == 0 or not volume.any():
        return {}
    max_id = int(volume.max())
    if max_id <= 2_000_000:
        from scipy import ndimage

        boxes = ndimage.find_objects(volume.astype(np.int64, copy=False) if volume.dtype.kind != "i" else volume)
        return {i + 1: b for i, b in enumerate(boxes) if b is not None}
    out = {}
    for i in np.unique(volume):
        if i == 0:
            continue
        idx = np.nonzero(volume == i)
        out[int(i)] = tuple(slice(int(a.min()), int(a.max()) + 1) for a in idx)
    return out


def bbox_center(bbox: Tuple[slice, ...]) -> np.ndarray:
    """Centre of a bounding box, in array index units (axis order of the box)."""
    return np.array([(s.start + s.stop - 1) / 2.0 for s in bbox])


def merge_labels(volume: np.ndarray, source_ids: Iterable[int], target_id: int) -> int:
    """Relabel ``source_ids`` to ``target_id`` in place; returns the number of voxels changed."""
    src = [int(s) for s in source_ids if int(s) != int(target_id)]
    if not src:
        return 0
    mask = np.isin(volume, src)
    n = int(mask.sum())
    volume[mask] = target_id
    return n


def delete_labels(volume: np.ndarray, ids: Iterable[int]) -> int:
    """Set ``ids`` to 0 in place; returns the number of voxels cleared."""
    return merge_labels(volume, ids, 0)


@dataclass
class InstanceRow:
    """One row of an instance browser."""

    instance_id: int
    count: int = 0
    score: Optional[float] = None
    length: Optional[float] = None
    color: Tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0)
    label: str = ""
    visible: bool = True
    key: Optional[int] = None  # unique key when instance IDs repeat (panoptic: the segment index)

    @property
    def row_key(self) -> int:
        return self.instance_id if self.key is None else self.key


def format_length(angstrom: Optional[float]) -> str:
    """A length given in Angstrom, in µm from 1 µm on and in nm below (e.g. ``1.42 µm``, ``842 nm``)."""
    if angstrom is None:
        return ""
    if abs(angstrom) >= 1e4:
        return f"{angstrom / 1e4:.2f} µm"
    return f"{angstrom / 10:.0f} nm"


def instance_row_title(row: InstanceRow, kind: str = "") -> str:
    """First line of a compact instance row: ``#12``; ``unassigned`` for picks without an ID; ``ribosome #3`` /
    ``membrane (stuff)`` for panoptic segments."""
    if kind == "panoptic":
        name = row.label or "segment"
        return f"{name} #{row.instance_id}" if row.instance_id else f"{name} (stuff)"
    if kind == "picks" and row.instance_id == 0:
        return row.label or "unassigned"
    return f"#{row.instance_id}"


def instance_row_caption(row: InstanceRow, kind: str = "") -> str:
    """Second line of a compact instance row: what the row's numbers mean for its kind; empty values are left out."""
    parts: List[str] = []
    if kind in ("instance", "panoptic"):
        parts.append(f"{row.count:,} voxels")
    elif kind == "filaments" and row.label == "pending":
        parts.append(f"pending · {row.count} control point{'s' if row.count != 1 else ''}")
    elif kind == "filaments":
        if row.length is not None:
            parts.append(format_length(row.length))
    else:
        parts.append(f"{row.count:,} pt{'s' if row.count != 1 else ''}")
    if row.score is not None:
        parts.append(f"score {row.score:.2f}")
    if (
        row.label
        and kind not in ("panoptic", "instance")
        and row.label != "pending"
        and not (kind == "picks" and row.instance_id == 0)
    ):
        parts.append(row.label)
    return " · ".join(parts)


def rows_from_points(
    instance_ids: Sequence[int],
    scores: Optional[Sequence[float]] = None,
    base_rgba: Sequence[float] = (1.0, 1.0, 1.0, 1.0),
) -> List[InstanceRow]:
    """Rows for points grouped by instance ID: point count and mean score. ID 0 (unassigned) gets a row too."""
    ids = np.asarray(instance_ids, dtype=np.int64).reshape(-1)
    sc = None if scores is None else np.asarray(scores, dtype=float).reshape(-1)
    rows = []
    for i in np.unique(ids):
        m = ids == i
        rows.append(
            InstanceRow(
                instance_id=int(i),
                count=int(m.sum()),
                score=None if sc is None else float(np.nanmean(sc[m])),
                color=tuple(base_rgba[:4]) if i == 0 else (*instance_rgb(i), 1.0),
                label="unassigned" if i == 0 else "",
            ),
        )
    return rows


def rows_from_filaments(filaments: Iterable, base_rgba: Sequence[float] = (1.0, 1.0, 1.0, 1.0)) -> List[InstanceRow]:
    """Rows for ``CopickFilament`` objects: point count, centreline length (Angstrom), score, curve kind."""
    from copick_shared_ui.util.filaments import polyline_length

    rows = []
    for f in filaments:
        pts = np.asarray(f.points, dtype=float)
        curve = getattr(f, "curve", None)
        rows.append(
            InstanceRow(
                instance_id=int(f.instance_id),
                count=len(pts),
                score=float(f.score),
                length=polyline_length(pts),
                color=(*instance_rgb(f.instance_id), 1.0),
                label=curve.kind if curve is not None else "",
            ),
        )
    return sorted(rows, key=lambda r: r.instance_id)


def rows_from_counts(counts: Dict[int, int], label: str = "") -> List[InstanceRow]:
    """Rows for an instance segmentation: voxel count per ID."""
    return [
        InstanceRow(instance_id=int(i), count=int(c), color=(*instance_rgb(i), 1.0), label=label)
        for i, c in sorted(counts.items())
    ]


def panoptic_segments(
    labels: np.ndarray,
    instances: np.ndarray,
    objects: Dict[int, Tuple[str, Sequence[float]]],
) -> Tuple[np.ndarray, List[InstanceRow]]:
    """Index the segments ``(label, instance)`` of a panoptic segmentation.

    Args:
        labels: Label channel (object labels, 0 = background).
        instances: Instance channel (per-object instance IDs, 0 = stuff / not split).
        objects: ``{label: (object_name, rgba floats 0-1)}``.

    Returns:
        A ``uint32`` volume where each segment has its own index (1..S, 0 = background), and one row per segment
        (``key`` = segment index, ``label`` = object name). Stuff segments (instance 0) use the object's colour,
        things their instance colour.
    """
    labels = np.asarray(labels)
    instances = np.asarray(instances)
    mask = labels != 0
    seg = np.zeros(labels.shape, dtype=np.uint32)
    if not mask.any():
        return seg, []
    keys = (labels[mask].astype(np.uint64) << np.uint64(32)) | instances[mask].astype(np.uint64)
    uniq, inverse, counts = np.unique(keys, return_inverse=True, return_counts=True)
    seg[mask] = (inverse + 1).astype(np.uint32)
    rows = []
    for index, (key, count) in enumerate(zip(uniq, counts), start=1):
        label = int(key >> np.uint64(32))
        inst = int(key & np.uint64(0xFFFFFFFF))
        name, rgba = objects.get(label, (str(label), (0.5, 0.5, 0.5, 1.0)))
        color = tuple(rgba[:4]) if inst == 0 else (*instance_rgb(inst), 1.0)
        rows.append(InstanceRow(instance_id=inst, count=int(count), color=color, label=name, key=index))
    return seg, rows
