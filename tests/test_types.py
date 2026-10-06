from types import SimpleNamespace

from copick_shared_ui.core import types as ct


def test_segmentation_type_of_new_and_fallback(project):
    root, _ = project
    run = root.new_run("r1")
    run.new_voxel_spacing(10.0)
    inst = run.new_segmentation(10.0, "ribosome", "1", user_id="u", is_instance=True)
    ml = run.new_segmentation(10.0, "labels", "1", user_id="u", is_multilabel=True)
    assert ct.segmentation_type_of(inst) == "instance"
    assert ct.segmentation_type_of(ml) == "multilabel"
    # old copick-like objects
    assert ct.segmentation_type_of(SimpleNamespace(is_multilabel=False)) == "binary"
    assert ct.segmentation_type_of(SimpleNamespace(is_multilabel=True)) == "multilabel"


def test_object_types(project):
    root, _ = project
    run = root.new_run("r1")
    picks = run.new_picks("ribosome", "1", user_id="u")
    fils = run.new_filaments("microtubule", "1", user_id="u")
    assert ct.copick_object_type(picks) == "picks"
    assert ct.copick_object_type(fils) == "filaments"
    assert ct.uri_object_type(fils) == "filaments"
    assert ct.uri_object_type(run) is None
    assert ct.copick_object_type(object()) is None


def test_filament_detection(project):
    root, _ = project
    assert ct.is_filament_object(root.get_object("microtubule"))
    assert not ct.is_filament_object(root.get_object("ribosome"))
    assert ct.filament_spec_of(root.get_object("microtubule")) == {"polar": True}
    # PickableObject (config level) and plain metadata dicts work too
    po = next(o for o in root.config.pickable_objects if o.name == "microtubule")
    assert ct.is_filament_object(po)
    legacy = SimpleNamespace(metadata={"copick": {"filament": {"polar": False}}})
    assert ct.filament_spec_of(legacy) == {"polar": False} and ct.is_filament_object(legacy)


def test_segmentation_type_flags():
    assert ct.segmentation_type_flags("binary") == {"is_multilabel": False, "is_instance": False, "is_panoptic": False}
    assert ct.segmentation_type_flags("instance")["is_instance"] is True
    assert ct.segmentation_type_flags("binary", explicit=False) == {"is_multilabel": False}
    assert ct.supports_filaments() and ct.supports_segmentation_types()


def test_delete_binary_keeps_same_key_instance(project):
    import numpy as np

    root, _ = project
    run = root.new_run("r1")
    run.new_voxel_spacing(10.0)
    run.new_segmentation(10.0, "ribosome", "1", user_id="u").from_numpy(np.ones((4, 4, 4), dtype=np.uint8))
    inst = run.new_segmentation(10.0, "ribosome", "1", user_id="u", is_instance=True)
    inst.from_numpy(np.full((4, 4, 4), 3, dtype=np.uint16))
    run.delete_segmentations(
        name="ribosome",
        user_id="u",
        session_id="1",
        voxel_size=10.0,
        **ct.segmentation_type_flags("binary"),
    )
    run.refresh_segmentations()
    assert [s.segmentation_type for s in run.segmentations] == ["instance"]
