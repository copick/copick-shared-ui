import pytest

from copick_shared_ui.widgets.cli.uri_widget import _assemble_uri, _parse_uri_simple


@pytest.mark.parametrize(
    "values, uri",
    [
        (
            {
                "object_name": "ribosome",
                "user_id": "u",
                "session_id": "1",
                "voxel_spacing": "10.0",
                "segmentation_type": "instance",
            },
            "ribosome:u/1@10.0?instance=true",
        ),
        (
            {
                "object_name": "labels",
                "user_id": "u",
                "session_id": "1",
                "voxel_spacing": "10.0",
                "segmentation_type": "multilabel",
            },
            "labels:u/1@10.0?multilabel=true",
        ),
        ({"object_name": "membrane", "user_id": "u", "session_id": "1", "voxel_spacing": "10.0"}, "membrane:u/1@10.0"),
    ],
)
def test_segmentation_uri_round_trip(values, uri):
    assert _assemble_uri("segmentation", values) == uri
    parsed = _parse_uri_simple("segmentation", uri)
    assert parsed["voxel_spacing"] == "10.0"  # the query does not leak into the voxel spacing
    assert parsed.get("segmentation_type", "") == values.get("segmentation_type", "")
    assert parsed["object_name"] == values["object_name"]


def test_filaments_uri():
    assert _assemble_uri("filaments", {"object_name": "microtubule", "user_id": "u", "session_id": "1"}) == (
        "microtubule:u/1"
    )
    assert _parse_uri_simple("filaments", "microtubule:u/1") == {
        "object_name": "microtubule",
        "user_id": "u",
        "session_id": "1",
    }


def test_edit_dialog_keeps_metadata_and_edits_filament(qtbot, project):
    from copick_shared_ui.ui.edit_object_types_dialog import EditObjectTypesDialog

    root, _ = project
    objs = [o.model_copy(deep=True) for o in root.config.pickable_objects]
    mt = next(o for o in objs if o.name == "microtubule")
    mt.metadata["copick"]["filament"]["custom_key"] = 1  # extra spec keys survive
    mt.metadata["other"] = {"keep": True}
    dlg = EditObjectTypesDialog(existing_objects=objs)
    qtbot.addWidget(dlg)
    row = [o.name for o in dlg.get_objects()].index("microtubule")
    dlg._objects_table.selectRow(row)
    dlg._edit_selected_object()
    assert dlg._is_filament_cb.isChecked() and dlg._polarity_combo.currentText() == "Polar"
    dlg._radius_spin.setValue(130.0)
    dlg._rise_spin.setValue(9.4)
    dlg._apply_changes()
    edited = next(o for o in dlg.get_objects() if o.name == "microtubule")
    assert edited.radius == 130.0
    assert edited.metadata["other"] == {"keep": True}
    assert edited.metadata["copick"]["filament"] == {"polar": True, "custom_key": 1, "helical_rise_a": 9.4}
    assert dlg.has_changes()
    # unchecking "Is Particle" removes the filament declaration
    dlg._objects_table.selectRow(row)
    dlg._edit_selected_object()
    dlg._is_particle_cb.setChecked(False)
    assert not dlg._is_filament_cb.isChecked()
    dlg._apply_changes()
    edited = next(o for o in dlg.get_objects() if o.name == "microtubule")
    assert "filament" not in edited.metadata.get("copick", {}) and edited.metadata["other"] == {"keep": True}


def test_instance_browser(qtbot):
    from copick_shared_ui.util.instances import InstanceRow
    from copick_shared_ui.widgets.instances import InstanceBrowserWidget

    w = InstanceBrowserWidget(title="Filaments")
    qtbot.addWidget(w)
    w.set_capabilities(new=True, delete=True, merge=True, reverse=True)
    w.set_rows([InstanceRow(i, count=10 * i) for i in (1, 2, 3)], kind="filaments")
    seen = []
    w.focus_requested.connect(seen.append)
    w.step(1)
    w.step(1)
    assert seen == [1, 2]
    vis = []
    w.visibility_changed.connect(vis.append)
    w.set_visible({1, 3})
    assert vis[-1] == {1, 3}
    w.step(1)  # skips hidden 2
    assert seen[-1] == 3
    # rows keep visibility across refresh
    w.set_rows([InstanceRow(i) for i in (1, 2, 3, 4)])
    assert w.visible_keys() == {1, 3, 4}
    merged = []
    w.merge_requested.connect(lambda s, t: merged.append((sorted(s), t)))
    w.set_current(2, emit=False)
    w._table.selectAll()
    w._on_merge()
    assert merged == [([1, 3, 4], 2)]
