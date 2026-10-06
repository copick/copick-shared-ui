import colorsys

import numpy as np
import pytest

from copick_shared_ui.util import instances as inst


def test_instance_rgb_matches_pr_formula():
    for i in (1, 2, 7, 300, 70001):
        assert inst.instance_rgb(i) == pytest.approx(colorsys.hsv_to_rgb((i * 0.618033988749895) % 1.0, 0.65, 0.95))


def test_instance_colors_float_and_uint8():
    base = (0.1, 0.2, 0.3, 0.5)
    c = inst.instance_colors([0, 3, 3, 5], base)
    assert c.shape == (4, 4)
    assert tuple(c[0]) == pytest.approx(base)
    assert tuple(c[1, :3]) == pytest.approx(inst.instance_rgb(3))
    assert c[1, 3] == pytest.approx(0.5)  # alpha from base
    u = inst.instance_colors([0, 3], (10, 20, 30, 255), dtype=np.uint8)
    assert u.dtype == np.uint8 and tuple(u[0]) == (10, 20, 30, 255)
    assert tuple(u[1, :3]) == tuple(np.round(np.array(inst.instance_rgb(3)) * 255).astype(np.uint8))


def test_color_table_and_dict():
    t = inst.instance_color_table(5, hidden=[2])
    assert t.shape == (6, 4) and t.dtype == np.uint8
    assert tuple(t[0]) == (0, 0, 0, 0) and tuple(t[2]) == (0, 0, 0, 0)
    assert t[3, 3] == 255
    d = inst.instance_color_dict([1, 4], alpha=0.5, hidden=[4])
    assert d[0][3] == 0 and d[4][3] == 0 and d[1][3] == 0.5


def test_next_instance_id():
    assert inst.next_instance_id() == 1
    assert inst.next_instance_id([], np.array([], dtype=int)) == 1
    assert inst.next_instance_id([3, 1], {7}, np.array([2])) == 8
    assert inst.next_instance_id({4: 10, 9: 1}.keys(), set()) == 10


@pytest.mark.parametrize(
    "text, expected",
    [("1-3, 5", {1, 2, 3, 5}), ("9", {9}), ("4 - 2;7", {2, 3, 4, 7}), ("", set()), ("1 2 3", {1, 2, 3})],
)
def test_parse_id_set(text, expected):
    assert inst.parse_id_set(text) == expected


def test_parse_id_set_rejects_garbage():
    with pytest.raises(ValueError):
        inst.parse_id_set("abc")


def test_format_id_set_round_trip():
    ids = {1, 2, 3, 5, 9, 10}
    assert inst.format_id_set(ids) == "1-3, 5, 9-10"
    assert inst.parse_id_set(inst.format_id_set(ids)) == ids


def test_counts_bboxes_merge_delete():
    v = np.zeros((4, 5, 6), dtype=np.uint16)
    v[0, 0, 0:2] = 1
    v[1:3, 1:4, 2] = 2
    v[3, 4, 5] = 300
    assert inst.label_counts(v) == {1: 2, 2: 6, 300: 1}
    boxes = inst.label_bboxes(v)
    assert boxes[2] == (slice(1, 3), slice(1, 4), slice(2, 3))
    assert inst.bbox_center(boxes[2]) == pytest.approx([1.5, 2.0, 2.0])
    assert inst.merge_labels(v, [1, 300], 2) == 3
    assert inst.label_counts(v) == {2: 9}
    assert inst.delete_labels(v, [2]) == 9 and not v.any()


def test_label_counts_large_dtype():
    v = np.array([0, 70001, 70001, 5], dtype=np.uint32)
    assert inst.label_counts(v) == {5: 1, 70001: 2}


def test_panoptic_segments():
    labels = np.array([[0, 2, 2, 3], [3, 3, 2, 0]], dtype=np.uint16)
    instance_ch = np.array([[0, 0, 0, 1], [1, 2, 0, 0]], dtype=np.uint16)
    objects = {2: ("membrane", (0.5, 0.5, 0.5, 1.0)), 3: ("ribosome", (1.0, 0.0, 0.0, 1.0))}
    seg, rows = inst.panoptic_segments(labels, instance_ch, objects)
    assert seg.dtype == np.uint32 and seg[0, 0] == 0
    by = {(r.label, r.instance_id): r for r in rows}
    assert set(by) == {("membrane", 0), ("ribosome", 1), ("ribosome", 2)}
    assert by[("membrane", 0)].count == 3 and by[("membrane", 0)].color == (0.5, 0.5, 0.5, 1.0)
    assert by[("ribosome", 1)].count == 2
    assert by[("ribosome", 1)].color[:3] == pytest.approx(inst.instance_rgb(1))
    # every voxel of a segment carries that segment's key
    assert set(np.unique(seg[(labels == 3) & (instance_ch == 1)])) == {by[("ribosome", 1)].key}


def test_rows_from_points():
    rows = inst.rows_from_points([0, 1, 1, 2], [0.5, 1.0, 0.0, 0.25])
    assert [(r.instance_id, r.count) for r in rows] == [(0, 1), (1, 2), (2, 1)]
    assert rows[1].score == pytest.approx(0.5)
    assert rows[0].label == "unassigned"
