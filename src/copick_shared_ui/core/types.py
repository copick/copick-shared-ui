"""Copick entity types as the UI sees them, tolerant of copick versions that predate filaments and the newer
segmentation types. Qt-free."""

from typing import Any, Optional

SEGMENTATION_TYPES = ("binary", "multilabel", "instance", "panoptic")

SEGMENTATION_TYPE_LABELS = {
    "binary": "Binary",
    "multilabel": "Multilabel",
    "instance": "Instance",
    "panoptic": "Panoptic",
}

# Short tags for compact tables and badges (the chips copick-web shows).
SEGMENTATION_TYPE_TAGS = {
    "binary": "binary",
    "multilabel": "multi",
    "instance": "inst",
    "panoptic": "pan",
}

FILAMENT_METADATA_NAMESPACE = "copick"
FILAMENT_METADATA_KEY = "filament"


def _class_names(obj: Any):
    return [cls.__name__ for cls in type(obj).__mro__]


def copick_object_type(obj: Any) -> Optional[str]:
    """``"filaments"``, ``"picks"``, ``"mesh"``, ``"segmentation"``, ``"tomogram"``, ``"feature"``, ``"voxel_spacing"``,
    ``"run"`` or None, by class (works for every backend's subclasses)."""
    names = _class_names(obj)
    # Order matters: check the more specific names first.
    for cls_name, kind in (
        ("CopickFilaments", "filaments"),
        ("CopickPicks", "picks"),
        ("CopickMesh", "mesh"),
        ("CopickSegmentation", "segmentation"),
        ("CopickTomogram", "tomogram"),
        ("CopickFeatures", "feature"),
        ("CopickVoxelSpacing", "voxel_spacing"),
        ("CopickRun", "run"),
    ):
        if cls_name in names:
            return kind
    return None


URI_OBJECT_TYPES = ("picks", "filaments", "mesh", "segmentation", "tomogram", "feature")


def uri_object_type(obj: Any) -> Optional[str]:
    """The copick URI object type of an entity (``copick.util.uri``), or None if it has no URI form."""
    if obj is None:
        return None
    kind = copick_object_type(obj)
    return kind if kind in URI_OBJECT_TYPES else None


def segmentation_type_of(seg: Any) -> str:
    """``"binary"``, ``"multilabel"``, ``"instance"`` or ``"panoptic"`` (falls back to ``is_multilabel`` for copick
    versions without instance and panoptic segmentations)."""
    kind = getattr(seg, "segmentation_type", None)
    if isinstance(kind, str) and kind in SEGMENTATION_TYPES:
        return kind
    if getattr(seg, "is_panoptic", False) is True:
        return "panoptic"
    if getattr(seg, "is_instance", False) is True:
        return "instance"
    return "multilabel" if getattr(seg, "is_multilabel", False) else "binary"


def segmentation_type_flags(kind: str, explicit: Optional[bool] = None) -> dict:
    """Keyword flags for ``new_segmentation`` / ``get_segmentations`` / ``delete_segmentations`` selecting exactly one
    type.

    With a copick that has instance and panoptic segmentations (``explicit``, detected by default), all three flags are
    given, because an omitted flag means "any": ``delete_segmentations(..., is_multilabel=False)`` alone would also
    delete an instance segmentation with the same name, user, session and voxel size. Older copick versions only get
    ``is_multilabel``.
    """
    if kind not in SEGMENTATION_TYPES:
        raise ValueError(f"Unknown segmentation type {kind!r}")
    explicit = supports_segmentation_types() if explicit is None else explicit
    if not explicit:
        if kind in ("instance", "panoptic"):
            raise ValueError(f"This copick version has no {kind} segmentations.")
        return {"is_multilabel": kind == "multilabel"}
    return {"is_multilabel": kind == "multilabel", "is_instance": kind == "instance", "is_panoptic": kind == "panoptic"}


def filament_spec_of(obj: Any) -> Optional[dict]:
    """The filament declaration of a pickable object (``PickableObject`` or ``CopickObject``) as a dict, or None."""
    spec = getattr(obj, "filament", None)
    if spec is not None and not callable(spec):
        return spec.model_dump(exclude_none=True) if hasattr(spec, "model_dump") else dict(spec)
    meta = getattr(obj, "metadata", None)
    if meta is None and hasattr(obj, "_meta"):
        meta = getattr(obj._meta, "metadata", None)
    if isinstance(meta, dict):
        ns = meta.get(FILAMENT_METADATA_NAMESPACE)
        if isinstance(ns, dict) and isinstance(ns.get(FILAMENT_METADATA_KEY), dict):
            return dict(ns[FILAMENT_METADATA_KEY])
    return None


def is_filament_object(obj: Any) -> bool:
    """Whether a pickable object is declared a filament."""
    value = getattr(obj, "is_filament", None)
    if isinstance(value, bool):
        return value
    return filament_spec_of(obj) is not None


def supports_filaments() -> bool:
    """Whether the installed copick has the Filaments entity."""
    try:
        from copick.models import CopickRun
    except ImportError:  # pragma: no cover
        return False
    return hasattr(CopickRun, "get_filaments")


def supports_segmentation_types() -> bool:
    """Whether the installed copick has instance and panoptic segmentations."""
    try:
        from copick.models import CopickSegmentation
    except ImportError:  # pragma: no cover
        return False
    return hasattr(CopickSegmentation, "segmentation_type")
