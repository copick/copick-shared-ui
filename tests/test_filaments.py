import numpy as np
import pytest

from copick_shared_ui.util import filaments as fil


def helix(n=200, r=50.0, pitch=400.0, turns=2.0):
    t = np.linspace(0, 2 * np.pi * turns, n)
    return np.stack([r * np.cos(t), r * np.sin(t), pitch * t / (2 * np.pi)], axis=1)


def test_resample_spacing_and_length():
    line = np.array([[0.0, 0, 0], [100.0, 0, 0]])
    pts = fil.resample_by_arc_length(line, 30.0)
    assert np.allclose(pts[:, 0], [0, 30, 60, 90])
    assert fil.resample_by_arc_length(line, 30.0, include_end=True)[-1, 0] == pytest.approx(100.0)
    assert fil.polyline_length(line) == pytest.approx(100.0)
    assert fil.point_at_arc_length(line, 0.5) == pytest.approx([50.0, 0, 0])


def test_frames_are_rotations_with_z_tangent_and_no_spin():
    pts = fil.resample_by_arc_length(helix(), 10.0)
    t = fil.polyline_tangents(pts)
    R = fil.parallel_transport_frames(t)
    for i in range(len(R)):
        assert np.allclose(R[i].T @ R[i], np.eye(3), atol=1e-9)
        assert np.linalg.det(R[i]) == pytest.approx(1.0)
        assert np.allclose(R[i][:, 2], t[i])
    # rotation-minimising: consecutive x axes stay close
    dots = np.einsum("ij,ij->i", R[1:, :, 0], R[:-1, :, 0])
    assert dots.min() > 0.95


def test_sample_filament_poses():
    pos, tr = fil.sample_filament_poses(np.array([[0.0, 0, 0], [0, 0, 100.0]]), 25.0)
    assert len(pos) == 5 and tr.shape == (5, 4, 4)
    assert np.allclose(tr[:, :3, 2], [0, 0, 1])
    assert np.allclose(tr[:, :3, 3], 0) and np.allclose(tr[:, 3], [0, 0, 0, 1])


def test_filaments_to_picks_groups_and_orders():
    from copick.models import CopickFilament

    a = CopickFilament.from_control_points(3, [[0, 0, 0], [0, 0, 200]], step=10.0, score=0.5)
    b = CopickFilament.from_control_points(7, [[100, 0, 0], [300, 0, 0]], step=10.0)
    pos, tr, ids, sc = fil.filaments_to_picks([a, b], spacing=50.0)
    assert list(ids) == [3] * 5 + [7] * 5
    assert np.allclose(sc[:5], 0.5) and np.allclose(sc[5:], 1.0)
    assert np.all(np.diff(pos[:5, 2]) > 0) and np.all(np.diff(pos[5:, 0]) > 0)
    assert np.allclose(tr[:5, :3, 2], [0, 0, 1]) and np.allclose(tr[5:, :3, 2], [1, 0, 0])


def test_filaments_to_picks_empty():
    pos, tr, ids, sc = fil.filaments_to_picks([], 10.0)
    assert pos.shape == (0, 3) and tr.shape == (0, 4, 4) and len(ids) == len(sc) == 0


def test_editable_handles_kinds():
    from copick.models import CopickFilament, CopickFilamentCurve

    cr = CopickFilament.from_control_points(1, [[0, 0, 0], [50, 10, 0], [100, 0, 0]], step=5.0)
    cps, kind, can = fil.editable_handles(cr)
    assert kind == "catmull-rom" and can and len(cps) == 3
    # a filament without a curve gets derived catmull-rom handles
    plain = CopickFilament(instance_id=2, points=[tuple(p) for p in cr.points])
    cps, kind, can = fil.editable_handles(plain)
    assert kind == "catmull-rom" and can and len(cps) >= 2
    # a bspline keeps its knots: handles can move but not be added/removed
    from scipy.interpolate import splprep

    pts = helix(60)
    tck, _ = splprep(pts.T, s=len(pts) * 4.0)
    bs = CopickFilament.from_curve(3, CopickFilamentCurve.from_tck(tck, step=5.0))
    cps, kind, can = fil.editable_handles(bs)
    assert kind == "bspline" and not can and len(cps) == len(bs.curve.control_points)


@pytest.mark.parametrize(
    "mode, point, index",
    [
        ("append", [5, 0, 0], 3),
        ("prepend", [5, 0, 0], 0),
        ("nearest", [15, 1, 0], 2),
        ("nearest", [-5, 0, 0], 0),
        ("nearest", [30, 0, 0], 3),
        ("nearest", [4, -1, 0], 1),
    ],
)
def test_insert_control_point(mode, point, index):
    cps = np.array([[0.0, 0, 0], [10, 0, 0], [20, 0, 0]])
    new, i = fil.insert_control_point(cps, point, mode)
    assert i == index and len(new) == 4 and np.allclose(new[i], point)


def test_insert_into_empty_and_single():
    new, i = fil.insert_control_point(np.zeros((0, 3)), [1, 2, 3], "nearest")
    assert i == 0 and new.shape == (1, 3)
    new, i = fil.insert_control_point(new, [4, 5, 6], "nearest")
    assert i == 1


def test_nearest_point_to_line():
    pts = np.array([[0.0, 0, 50], [0, 0, 10], [30, 0, 10]])
    # ray along -z from z=100 down to z=-100 passing x=y=0: hits (0,0,50) first
    assert fil.nearest_point_to_line(pts, [0, 0, 100], [0, 0, -100], 2.0) == 0
    assert fil.nearest_point_to_line(pts, [30, 0, 100], [30, 0, -100], 2.0) == 2
    assert fil.nearest_point_to_line(pts, [15, 0, 100], [15, 0, -100], 2.0) is None


def test_nearest_on_polyline_respects_order_on_a_hairpin():
    from copick_shared_ui.util.filaments import nearest_on_polyline

    # out along y=0, back along y=10: a point near the start is near both legs
    line = np.array([[0, 0, 0], [100, 0, 0], [100, 10, 0], [0, 10, 0]], dtype=float)
    s, p, d = nearest_on_polyline(line, [20, 4, 0])
    assert s == pytest.approx(20) and d == pytest.approx(4)
    s, p, d = nearest_on_polyline(line, [20, 4, 0], from_arc_length=110)
    assert s == pytest.approx(190) and np.allclose(p, [20, 10, 0])


def test_direction_markers_point_along_the_filament():
    from copick_shared_ui.util.filaments import direction_markers

    line = np.array([[0, 0, 0], [1000, 0, 0], [1000, 1000, 0]], dtype=float)
    pos, d = direction_markers(line, spacing=400.0)
    assert len(pos) == len(d) >= 5
    assert np.allclose(np.linalg.norm(d, axis=1), 1.0)
    assert np.allclose(d[0], [1, 0, 0]) and np.allclose(d[-1], [0, 1, 0])  # first leg along x, last along y
    assert np.allclose(pos[0], [200, 0, 0]) and pos[-1][1] >= 900  # starts half a spacing in, ends near the end
    rpos, rd = direction_markers(line[::-1], spacing=400.0)
    assert np.allclose(rd[-1], [-1, 0, 0])  # reversed: arrows flip
