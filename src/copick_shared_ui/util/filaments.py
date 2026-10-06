"""Filament helpers for the viewers: sampling picks along centrelines, tangent frames, and control-point editing.

Curves themselves (evaluation, regeneration of ``points``, derived handles, reversal, the stale-curve check) come from
copick core (``CopickFilament.from_control_points`` / ``with_control_points`` / ``editable_curve`` / ``reversed`` and
``copick.util.filaments``); nothing here re-implements them. Qt-free, numpy only.

Conventions (copick ``geometry.md`` 2.4): picks of a filament object are grouped by filament, ordered along it, carry
the filament's ``instance_id``, and their transform's +Z axis is the local tangent in point order.
"""

from typing import Iterable, List, Optional, Sequence, Tuple

import numpy as np

EDITABLE_KINDS = ("catmull-rom", "linear", "bspline")


def polyline_length(points: np.ndarray) -> float:
    """Length of a polyline (same units as the points)."""
    pts = np.asarray(points, dtype=float).reshape(-1, 3)
    if len(pts) < 2:
        return 0.0
    return float(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum())


def _arc_lengths(points: np.ndarray) -> np.ndarray:
    seg = np.linalg.norm(np.diff(points, axis=0), axis=1)
    return np.concatenate([[0.0], np.cumsum(seg)])


def point_at_arc_length(points: np.ndarray, fraction: float = 0.5) -> np.ndarray:
    """The point a ``fraction`` of the way along a polyline (0.5 = midpoint by length)."""
    pts = np.asarray(points, dtype=float).reshape(-1, 3)
    if len(pts) == 1:
        return pts[0].copy()
    s = _arc_lengths(pts)
    target = float(np.clip(fraction, 0.0, 1.0)) * s[-1]
    return np.array([np.interp(target, s, pts[:, i]) for i in range(3)])


def resample_by_arc_length(points: np.ndarray, spacing: float, include_end: bool = False) -> np.ndarray:
    """Points ``spacing`` apart along a polyline, starting at its first point.

    Args:
        points: (M, 3) ordered polyline.
        spacing: Distance between samples (same units as the points), > 0.
        include_end: Also add the last point if it is not already a sample.
    """
    if spacing <= 0:
        raise ValueError("spacing must be positive")
    pts = np.asarray(points, dtype=float).reshape(-1, 3)
    if len(pts) < 2:
        return pts.copy()
    s = _arc_lengths(pts)
    targets = np.arange(0.0, s[-1] + 1e-9, spacing)
    if include_end and s[-1] - targets[-1] > 1e-6:
        targets = np.append(targets, s[-1])
    return np.stack([np.interp(targets, s, pts[:, i]) for i in range(3)], axis=1)


def polyline_tangents(points: np.ndarray) -> np.ndarray:
    """Unit tangents in point order (central differences inside, one-sided at the ends)."""
    pts = np.asarray(points, dtype=float).reshape(-1, 3)
    if len(pts) < 2:
        return np.tile([0.0, 0.0, 1.0], (len(pts), 1))
    t = np.gradient(pts, axis=0)
    norms = np.linalg.norm(t, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return t / norms


def parallel_transport_frames(tangents: np.ndarray, reference: Optional[Sequence[float]] = None) -> np.ndarray:
    """Rotation-minimising frames along a curve: (N, 3, 3) matrices whose columns are x, y, z with z = tangent.

    The first frame's x axis is ``reference`` (default the coordinate axis least aligned with the first tangent)
    made orthogonal to the tangent; later x axes are transported along the curve, so the frame does not spin.
    """
    t = np.asarray(tangents, dtype=float).reshape(-1, 3)
    n = len(t)
    frames = np.zeros((n, 3, 3))
    if n == 0:
        return frames
    if reference is None:
        reference = np.eye(3)[int(np.argmin(np.abs(t[0])))]
    x = np.asarray(reference, dtype=float) - t[0] * float(np.dot(reference, t[0]))
    if np.linalg.norm(x) < 1e-9:
        x = np.eye(3)[int(np.argmin(np.abs(t[0])))] - t[0] * t[0][int(np.argmin(np.abs(t[0])))]
    x /= np.linalg.norm(x)
    for i in range(n):
        if i:
            x = x - t[i] * float(np.dot(x, t[i]))
            norm = np.linalg.norm(x)
            if norm < 1e-9:  # tangent flipped onto x; restart from a fresh orthogonal axis
                x = np.eye(3)[int(np.argmin(np.abs(t[i])))] - t[i] * t[i][int(np.argmin(np.abs(t[i])))]
                norm = np.linalg.norm(x)
            x /= norm
        frames[i, :, 0] = x
        frames[i, :, 1] = np.cross(t[i], x)
        frames[i, :, 2] = t[i]
    return frames


def sample_filament_poses(points: np.ndarray, spacing: float) -> Tuple[np.ndarray, np.ndarray]:
    """Sample a centreline every ``spacing``: positions (N, 3) and transforms (N, 4, 4) with +Z along the tangent and
    no translation."""
    pos = resample_by_arc_length(points, spacing)
    if len(pos) < 2:
        tangents = polyline_tangents(np.asarray(points, dtype=float).reshape(-1, 3))[:1]
    else:
        tangents = polyline_tangents(pos)
    frames = parallel_transport_frames(tangents)
    transforms = np.tile(np.eye(4), (len(pos), 1, 1))
    transforms[:, :3, :3] = frames
    return pos, transforms


def filaments_to_picks(
    filaments: Iterable,
    spacing: float,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Picks sampled along ``CopickFilament`` centrelines, grouped by filament (file order) and ordered along each.

    Returns:
        positions (N, 3), transforms (N, 4, 4), instance_ids (N,) and scores (N,), ready for
        ``CopickPicks.from_numpy(positions, transforms, instance_ids=..., scores=...)``.
    """
    pos, tr, ids, sc = [], [], [], []
    for f in filaments:
        p, t = sample_filament_poses(np.asarray(f.points, dtype=float), spacing)
        pos.append(p)
        tr.append(t)
        ids.append(np.full(len(p), int(f.instance_id), dtype=np.int64))
        sc.append(np.full(len(p), float(f.score)))
    if not pos:
        return np.zeros((0, 3)), np.zeros((0, 4, 4)), np.zeros(0, dtype=np.int64), np.zeros(0)
    return np.concatenate(pos), np.concatenate(tr), np.concatenate(ids), np.concatenate(sc)


def editable_handles(filament, kinds: Sequence[str] = EDITABLE_KINDS) -> Tuple[np.ndarray, str, bool]:
    """The handles an editor shows for a ``CopickFilament``.

    Returns:
        ``(control_points (n, 3), kind, can_add_remove)``. A current curve of one of ``kinds`` is reused; otherwise core
        derives a ``catmull-rom`` curve from the points. A ``bspline`` keeps its knots, so its handles can be moved but
        not added or removed.
    """
    curve = filament.editable_curve(kinds=tuple(kinds))
    return np.asarray(curve.control_points, dtype=float), curve.kind, curve.kind != "bspline"


def insert_control_point(
    control_points: np.ndarray,
    point: Sequence[float],
    mode: str = "append",
) -> Tuple[np.ndarray, int]:
    """Insert ``point`` into an ordered control-point list.

    Args:
        control_points: (n, 3) existing control points (n may be 0).
        point: The new point.
        mode: ``"append"`` (after the last), ``"prepend"`` (before the first), or ``"nearest"`` (into the segment it is
            closest to; before the first or after the last if it lies beyond an end).

    Returns:
        The new (n + 1, 3) array and the index of the inserted point.
    """
    cps = np.asarray(control_points, dtype=float).reshape(-1, 3)
    p = np.asarray(point, dtype=float).reshape(3)
    if mode == "prepend":
        index = 0
    elif mode == "append" or (mode == "nearest" and len(cps) < 2):
        index = len(cps)
    elif mode == "nearest":
        a, b = cps[:-1], cps[1:]
        ab = b - a
        denom = np.einsum("ij,ij->i", ab, ab)
        denom[denom == 0] = 1.0
        t = np.einsum("ij,ij->i", p - a, ab) / denom
        closest = a + np.clip(t, 0, 1)[:, None] * ab
        seg = int(np.argmin(np.linalg.norm(closest - p, axis=1)))
        if seg == 0 and t[0] < 0:
            index = 0
        elif seg == len(ab) - 1 and t[-1] > 1:
            index = len(cps)
        else:
            index = seg + 1
    else:
        raise ValueError(f"Unknown insert mode {mode!r}")
    return np.insert(cps, index, p, axis=0), index


def nearest_point_to_line(
    points: np.ndarray,
    line_start: Sequence[float],
    line_end: Sequence[float],
    tolerance: float,
) -> Optional[int]:
    """Index of the point closest to the viewer along a pick ray, if any lies within ``tolerance`` of it.

    Args:
        points: (n, 3) candidate points.
        line_start, line_end: The ray from the near to the far clip plane.
        tolerance: Largest distance from the ray (same units as the points).
    """
    pts = np.asarray(points, dtype=float).reshape(-1, 3)
    if len(pts) == 0:
        return None
    a = np.asarray(line_start, dtype=float)
    d = np.asarray(line_end, dtype=float) - a
    length = np.linalg.norm(d)
    if length == 0:
        return None
    d /= length
    rel = pts - a
    along = rel @ d
    dist = np.linalg.norm(rel - along[:, None] * d, axis=1)
    ok = np.nonzero((dist <= tolerance) & (along >= 0) & (along <= length))[0]
    if len(ok) == 0:
        return None
    return int(ok[np.argmin(along[ok])])


def nearest_on_polyline(
    points: np.ndarray,
    query: Sequence[float],
    from_arc_length: float = 0.0,
) -> Tuple[float, np.ndarray, float]:
    """The point of a polyline closest to ``query``: ``(arc length, point, distance)``.

    Args:
        points: (n, 3) polyline, n >= 2.
        query: The point to project.
        from_arc_length: Only consider the polyline from this arc length on (keeps projections of successive points
            in order on a filament that passes close to itself).
    """
    pts = np.asarray(points, dtype=float).reshape(-1, 3)
    q = np.asarray(query, dtype=float)
    start, d = pts[:-1], np.diff(pts, axis=0)
    seg_len = np.linalg.norm(d, axis=1)
    safe_len = np.where(seg_len > 0, seg_len, 1.0)
    s0 = _arc_lengths(pts)[:-1]
    t = np.einsum("ij,ij->i", q - start, d) / safe_len**2
    t_min = np.clip((from_arc_length - s0) / safe_len, 0.0, 1.0)  # no point before from_arc_length
    t = np.clip(np.maximum(t, t_min), 0.0, 1.0)
    closest = start + t[:, None] * d
    dist = np.linalg.norm(closest - q, axis=1)
    dist[s0 + seg_len < from_arc_length] = np.inf
    i = int(np.argmin(dist))
    s = s0 + t * seg_len
    return float(s[i]), closest[i], float(dist[i])


def split_control_points(
    controls: np.ndarray,
    polyline: np.ndarray,
    cut: Sequence[float],
    min_gap: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """Split the control points of an interpolating curve (Catmull-Rom, linear) at a point on its centreline.

    The cut point becomes the last control point of the first piece and the first of the second, so both pieces keep
    the curve's shape away from the cut. A cut within ``min_gap`` (arc length) of a control point splits at that
    control point instead.

    Args:
        controls: (n, 3) control points, in order along the curve.
        polyline: (m, 3) the centreline regenerated from them.
        cut: A point on (or near) the centreline.
        min_gap: Smallest arc length between the cut and a control point.

    Returns:
        The control points of the two pieces.

    Raises:
        ValueError: If a piece would have fewer than two control points (the cut is too close to an end).
    """
    cps = np.asarray(controls, dtype=float).reshape(-1, 3)
    line = np.asarray(polyline, dtype=float).reshape(-1, 3)
    s_cut, at, _ = nearest_on_polyline(line, cut)
    s_cps, s_prev = [], 0.0
    for c in cps:
        s_prev = nearest_on_polyline(line, c, from_arc_length=s_prev)[0]
        s_cps.append(s_prev)
    s_cps = np.asarray(s_cps)
    near = np.nonzero(np.abs(s_cps - s_cut) < min_gap)[0]
    if len(near):
        k = int(near[np.argmin(np.abs(s_cps[near] - s_cut))])
        first, second = cps[: k + 1], cps[k:]
    else:
        k = int(np.searchsorted(s_cps, s_cut)) - 1  # last control point before the cut
        first = np.vstack([cps[: k + 1], at]) if k >= 0 else at[None]
        second = np.vstack([at, cps[k + 1 :]])
    if len(first) < 2 or len(second) < 2:
        raise ValueError("The cut is too close to an end of the filament.")
    return first, second


def split_polyline(polyline: np.ndarray, cut: Sequence[float], min_gap: float) -> Tuple[np.ndarray, np.ndarray]:
    """Split a polyline at the point closest to ``cut``; both pieces include that point.

    Raises:
        ValueError: If a piece would be shorter than ``min_gap``.
    """
    line = np.asarray(polyline, dtype=float).reshape(-1, 3)
    s_cut, at, _ = nearest_on_polyline(line, cut)
    s = _arc_lengths(line)
    if s_cut < min_gap or s[-1] - s_cut < min_gap:
        raise ValueError("The cut is too close to an end of the filament.")
    first = np.vstack([line[s < s_cut], at])
    second = np.vstack([at, line[s > s_cut]])
    return first, second


def direction_markers(points: np.ndarray, spacing: float) -> Tuple[np.ndarray, np.ndarray]:
    """Where to draw arrows showing a filament's direction (its point order, what "reverse" flips).

    Returns ``(positions, directions)``: (K, 3) points along the polyline, half a ``spacing`` in and then every
    ``spacing``, plus one just before its end; (K, 3) unit vectors pointing along the filament there.
    """
    pts = np.asarray(points, dtype=float).reshape(-1, 3)
    if len(pts) < 2:
        return np.zeros((0, 3)), np.zeros((0, 3))
    s = _arc_lengths(pts)
    total = s[-1]
    if total <= 0:
        return np.zeros((0, 3)), np.zeros((0, 3))
    targets = list(np.arange(spacing / 2, total - spacing / 4, spacing)) if spacing > 0 else []
    end = max(0.0, total - min(spacing / 4, total / 10) if spacing > 0 else total * 0.9)
    targets.append(end)
    targets = np.asarray(targets)
    positions = np.stack([np.interp(targets, s, pts[:, i]) for i in range(3)], axis=1)
    seg = np.clip(np.searchsorted(s, targets, side="right") - 1, 0, len(pts) - 2)
    directions = pts[seg + 1] - pts[seg]
    norms = np.linalg.norm(directions, axis=1)
    keep = norms > 0
    return positions[keep], directions[keep] / norms[keep, None]


def filament_ids(filaments: Iterable) -> List[int]:
    """Instance IDs of ``CopickFilament`` objects."""
    return [int(f.instance_id) for f in filaments]
