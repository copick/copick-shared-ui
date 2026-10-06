import numpy as np
import pytest

from copick_shared_ui.util.filament_session import FilamentEditSession


@pytest.fixture
def run(project):
    root, _ = project
    r = root.new_run("r1")
    r.new_voxel_spacing(10.0)
    return r


def test_trace_new_filaments_and_save_with_picks(run):
    s = FilamentEditSession(run, "microtubule", "tracer", "1", step=10.0)
    assert s.active_id == 1 and not s.read_only
    s.insert_point([0, 0, 0])
    assert s.ids() == [1] and 1 in s.pending and not s.polylines()
    s.insert_point([100, 0, 0])
    s.insert_point([200, 50, 0])
    assert len(s.controls(1)) == 3 and s.kind(1) == "catmull-rom"
    line = s.polylines()[1]
    assert np.allclose(line[0], [0, 0, 0]) and np.allclose(line[-1], [200, 50, 0])
    assert np.linalg.norm(np.diff(line, axis=0), axis=1).max() <= 10.0 + 1e-6
    # nearest insert lands between the existing points
    s.insert_point([50, -5, 0], mode="nearest")
    assert np.allclose(s.controls(1)[1], [50, -5, 0])
    s.new_filament()
    assert s.active_id == 2
    s.insert_point([0, 300, 0])
    s.insert_point([0, 300, 200])
    res = s.save(pick_spacing=40.0)
    assert res["n_filaments"] == 2 and res["n_picks"] > 0
    fil = run.get_filaments(object_name="microtubule", user_id="tracer", session_id="1")[0]
    fil.refresh()
    assert sorted(fil.instance_ids().tolist()) == [1, 2]
    assert all(f.curve_is_current() and f.curve.kind == "catmull-rom" for f in fil.filaments)
    picks = run.get_picks(object_name="microtubule", user_id="tracer", session_id="1")[0]
    assert set(picks.instance_ids().tolist()) == {1, 2}
    assert not s.dirty


def test_reopen_edit_reverse_delete(run):
    s = FilamentEditSession(run, "microtubule", "tracer", "1", step=10.0)
    for p in ([0, 0, 0], [100, 0, 0], [200, 0, 0]):
        s.insert_point(p)
    s.save()
    fil = run.get_filaments(object_name="microtubule", user_id="tracer", session_id="1")[0]
    s2 = FilamentEditSession.from_filaments(fil)
    assert np.allclose(s2.controls(1), [[0, 0, 0], [100, 0, 0], [200, 0, 0]])
    s2.move_point(1, 1, [100, 40, 0])
    assert s2.dirty and s2.filaments[1].curve_is_current()
    s2.reverse(1)
    assert np.allclose(s2.controls(1)[0], [200, 0, 0])
    s2.remove_point(1, 0)
    assert len(s2.controls(1)) == 2
    s2.delete_filament(1)
    assert s2.ids() == [] and s2.to_list() == []


def test_bspline_handles_fixed_count_and_convert(run):
    from copick.models import CopickFilament, CopickFilamentCurve
    from scipy.interpolate import splprep

    t = np.linspace(0, 3 * np.pi, 80)
    pts = np.stack([300 * np.cos(t / 3), 300 * np.sin(t / 3), 20 * t], axis=1)
    tck, _ = splprep(pts.T, s=len(pts) * 9.0)
    fil = run.new_filaments("microtubule", "0", user_id="fit")
    fil.filaments = [CopickFilament.from_curve(1, CopickFilamentCurve.from_tck(tck, step=10.0))]
    fil.meta.voxel_spacing = 10.0
    fil.store()
    s = FilamentEditSession.from_filaments(fil)
    assert s.read_only  # session 0
    assert s.kind(1) == "bspline" and not s.can_add_remove(1)
    n = len(s.controls(1))
    cps = s.controls(1)
    cps[2] += [0, 0, 30]
    s.move_point(1, 2, cps[2])
    assert s.kind(1) == "bspline" and len(s.controls(1)) == n and s.filaments[1].curve_is_current()
    with pytest.raises(ValueError):
        s.insert_point([0, 0, 0], instance_id=1)
    s.convert_to_catmull_rom(1)
    assert s.kind(1) == "catmull-rom" and s.can_add_remove(1)
    s.insert_point([0, 0, 0], instance_id=1, mode="prepend")
    # saving a tool session under a user identity
    res = s.save(user_id="me", session_id="2")
    assert res["filaments"].session_id == "2" and res["filaments"].filaments[0].curve.kind == "catmull-rom"


def test_filament_without_curve_gets_derived_handles(run):
    from copick.models import CopickFilament

    line = [(float(x), 0.0, 0.0) for x in range(0, 201, 10)]
    fil = run.new_filaments("microtubule", "1", user_id="u")
    fil.filaments = [CopickFilament(instance_id=5, points=line)]
    fil.meta.voxel_spacing = 10.0
    fil.store()
    s = FilamentEditSession.from_filaments(fil)
    assert s.kind(5) == "catmull-rom" and len(s.controls(5)) >= 2
    s.move_point(5, 0, [0, 20, 0])
    assert s.filaments[5].curve is not None and s.filaments[5].curve_is_current()


def test_undo_redo_steps_and_grouped_drag(run):
    s = FilamentEditSession(run, "microtubule", "tracer", "1", step=10.0)
    recorded = []
    s.on_history = recorded.append
    s.insert_point([0, 0, 0])
    s.insert_point([100, 0, 0])
    s.insert_point([200, 0, 0])
    assert recorded == ["Add filament point"] * 3 and s.can_undo and not s.can_redo

    # a drag (many moves) is one step
    s.begin_step("Move filament point")
    for x in (110, 120, 130):
        s.move_point(1, 1, [x, 10, 0])
    s.end_step()
    assert recorded[-1] == "Move filament point" and len(recorded) == 4
    assert np.allclose(s.controls(1)[1], [130, 10, 0])

    assert s.undo() == "Move filament point"
    assert np.allclose(s.controls(1)[1], [100, 0, 0])  # back before the whole drag
    assert s.undo() == "Add filament point"
    assert len(s.controls(1)) == 2
    assert s.redo() == "Add filament point" and len(s.controls(1)) == 3
    assert s.redo() == "Move filament point" and np.allclose(s.controls(1)[1], [130, 10, 0])
    assert s.redo() is None

    # undoing down to one point makes the filament pending again, and the curve regenerates on redo
    s.undo(), s.undo(), s.undo()
    assert 1 in s.pending and 1 not in s.filaments
    s.redo()
    assert s.filaments[1].curve_is_current()

    # a new edit clears the redo stack
    s.insert_point([0, 50, 0])
    assert not s.can_redo


def test_undo_filament_level_edits(run):
    s = FilamentEditSession(run, "microtubule", "tracer", "1", step=10.0)
    for p in ([0, 0, 0], [100, 0, 0], [200, 0, 0]):
        s.insert_point(p)
    before = s.controls(1)
    s.reverse(1)
    assert np.allclose(s.controls(1), before[::-1])
    assert s.undo() == "Reverse filament" and np.allclose(s.controls(1), before)

    s.new_filament()
    assert s.active_id == 2
    assert s.undo() == "New filament" and s.active_id == 1

    s.delete_filament(1)
    assert s.ids() == []
    assert s.undo() == "Delete filament" and s.ids() == [1] and np.allclose(s.controls(1), before)

    # no-ops and failed edits record nothing
    n = len(s._undo)
    s.delete_filament(99)
    s.reverse(99)
    s.begin_step("nothing")
    s.end_step()
    assert len(s._undo) == n

    # undo after saving marks the set dirty again
    s.save()
    assert not s.dirty
    s.undo()
    assert s.dirty


def _straight(s, instance_id=None, n=5):
    for x in np.linspace(0, 400, n):
        s.insert_point([x, 0.0, 0.0], instance_id=instance_id)


def test_cut_catmull_rom_keeps_handles_and_is_undoable(run):
    s = FilamentEditSession(run, "microtubule", "tracer", "1", step=10.0)
    for p in ([0, 0, 0], [100, 50, 0], [200, 0, 0], [300, 50, 0], [400, 0, 0]):
        s.insert_point(p)
    before = s.controls(1)
    s.filaments[1] = s.filaments[1].model_copy(update={"score": 0.7, "polarity_known": True})
    near = s.filaments[1].points[len(s.filaments[1].points) // 2 + 3]  # just past the middle control point
    a, b = s.cut(np.asarray(near) + [0, 0, 5.0], tolerance=20.0)
    assert (a, b) == (1, 2)
    ca, cb = s.controls(1), s.controls(2)
    assert np.allclose(ca[:3], before[:3]) and np.allclose(cb[1:], before[3:])  # untouched handles
    assert np.allclose(ca[-1], cb[0])  # the cut point ends one piece and starts the other
    for i in (1, 2):
        f = s.filaments[i]
        assert f.curve.kind == "catmull-rom" and f.curve_is_current()
        assert f.score == 0.7 and f.polarity_known
    assert np.allclose(s.filaments[1].points[-1], s.filaments[2].points[0], atol=1e-6)

    assert s.undo() == "Cut filament"
    assert s.ids() == [1] and np.allclose(s.controls(1), before)
    assert s.redo() == "Cut filament" and s.ids() == [1, 2]


def test_cut_at_a_control_point_and_errors(run):
    s = FilamentEditSession(run, "microtubule", "tracer", "1", step=10.0)
    _straight(s)  # control points every 100 Å
    a, b = s.cut([203, 4, 0])  # within one step of the middle control point: split there
    assert len(s.controls(a)) == 3 and len(s.controls(b)) == 3
    assert np.allclose(s.controls(a)[-1], [200, 0, 0]) and np.allclose(s.controls(b)[0], [200, 0, 0])

    with pytest.raises(ValueError, match="too close to an end"):
        s.cut([2, 0, 0], instance_id=a)
    with pytest.raises(ValueError, match="No filament within"):
        s.cut([100, 500, 0], tolerance=50.0)
    assert s.nearest_filament([390, 10, 0])[0] == b


def test_cut_linear_and_bspline(run):
    from copick.models import CopickFilament, CopickFilamentCurve

    s = FilamentEditSession(run, "microtubule", "tracer", "1", step=10.0)
    s.filaments[1] = CopickFilament.from_control_points(
        1,
        [[0, 0, 0], [200, 0, 0], [400, 100, 0]],
        step=10.0,
        kind="linear",
    )
    s.cut([100, 0, 0])
    assert s.kind(1) == "linear" and s.kind(2) == "linear"

    t = np.linspace(0, 1, 8)
    ctrl = np.stack([t * 400, 60 * np.sin(t * 3), np.zeros_like(t)], axis=1)
    knots = np.concatenate([[0, 0, 0], np.linspace(0, 1, 6), [1, 1, 1]])
    curve = CopickFilamentCurve(kind="bspline", control_points=ctrl.tolist(), step=10.0, degree=3, knots=knots.tolist())
    s.filaments[5] = CopickFilament.from_curve(5, curve)
    pts = np.asarray(s.filaments[5].points)
    mid = pts[len(pts) // 2]
    a, b = s.cut(mid, instance_id=5)
    assert s.kind(a) == "catmull-rom" and s.kind(b) == "catmull-rom"
    joined = np.vstack([s.filaments[a].points, s.filaments[b].points])
    from copick.util.filaments import distances_to_polyline

    assert distances_to_polyline(joined, pts).max() < 10.0  # the pieces follow the fit within half a step-ish


def test_cut_keeps_an_empty_new_filament_active(run):
    s = FilamentEditSession(run, "microtubule", "tracer", "1", step=10.0)
    _straight(s)
    s.new_filament()
    assert s.active_id == 2 and 2 not in s.ids()
    a, b = s.cut([150, 0, 0])
    assert (a, b) == (1, 3) and s.active_id == 2


def test_delete_keeps_the_position(run):
    s = FilamentEditSession(run, "microtubule", "tracer", "1", step=10.0)
    for i in (1, 2, 3):
        _straight(s, instance_id=i)
    s.active_id = 2
    s.delete_filament(2)
    assert s.active_id == 3  # the next one, as removing a particle steps on
    s.delete_filament(3)
    assert s.active_id == 1  # the previous one at the end
    s.undo()
    assert s.active_id == 3


def test_join_chains_nearest_ends_and_is_undoable(run):
    s = FilamentEditSession(run, "microtubule", "tracer", "1", step=10.0)
    for x in (0, 100, 200):
        s.insert_point([x, 0, 0], instance_id=1)
    for x in (600, 500, 400):  # traced backwards: joining must flip it
        s.insert_point([x, 0, 0], instance_id=2)
    for x in (-400, -300, -200):  # before the start of 1
        s.insert_point([x, 0, 0], instance_id=3)
    s.filaments[1] = s.filaments[1].model_copy(update={"score": 0.8})
    before = {i: s.filaments[i] for i in (1, 2, 3)}
    target = s.join([2, 3, 1], target=1)
    assert target == 1 and s.ids() == [1] and s.active_id == 1
    cps = s.controls(1)
    assert np.allclose(cps[:, 0], [-400, -300, -200, 0, 100, 200, 400, 500, 600])  # ordered along 1's direction
    f = s.filaments[1]
    assert f.curve_is_current() and f.score == 0.8
    assert s.undo() == "Join filaments"
    assert s.ids() == [1, 2, 3] and all(s.filaments[i] == before[i] for i in (1, 2, 3))
    with pytest.raises(ValueError, match="at least two"):
        s.join([1])


def test_join_touching_ends_keeps_one_point_and_bspline_parts(run):
    from copick.models import CopickFilament, CopickFilamentCurve

    s = FilamentEditSession(run, "microtubule", "tracer", "1", step=10.0)
    s.filaments[1] = CopickFilament.from_control_points(1, [[0, 0, 0], [100, 0, 0]], step=10.0, kind="linear")
    s.filaments[2] = CopickFilament.from_control_points(2, [[100, 0, 0], [200, 50, 0]], step=10.0, kind="linear")
    s.join([1, 2])
    assert s.kind(1) == "linear" and len(s.controls(1)) == 3  # the shared end point once

    t = np.linspace(0, 1, 8)
    ctrl = np.stack([300 + t * 400, 60 * np.sin(t * 3), np.zeros_like(t)], axis=1)
    knots = np.concatenate([[0, 0, 0], np.linspace(0, 1, 6), [1, 1, 1]])
    curve = CopickFilamentCurve(kind="bspline", control_points=ctrl.tolist(), step=10.0, degree=3, knots=knots.tolist())
    s.filaments[5] = CopickFilament.from_curve(5, curve)
    s.join([1, 5])
    assert s.ids() == [1] and s.kind(1) == "catmull-rom" and s.filaments[1].curve_is_current()
