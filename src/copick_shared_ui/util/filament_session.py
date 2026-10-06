"""Editing state for one set of traced filaments (one object / user / session in one run), shared by the napari and
ChimeraX tracers. Qt-free.

The session holds ``CopickFilament`` models; every edit goes through copick core (``from_control_points``,
``with_control_points``, ``reversed``), so ``points`` are always regenerated from the curve by the normative algorithm
and saving never stores a stale curve. Viewers only translate clicks into control-point edits and redraw from
``polylines()`` / ``controls()``.

Every edit is one step of an undo/redo history (``undo()`` / ``redo()``). Edits that belong together, such as the
moves of one drag, are grouped with ``begin_step()`` / ``end_step()`` or ``with session.history_step(...)``. Viewers that have
their own undo stack (ChimeraX) set ``on_history`` to mirror each new step there.
"""

from contextlib import contextmanager
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence, Tuple

import numpy as np

from copick_shared_ui.util.filaments import (
    editable_handles,
    filaments_to_picks,
    insert_control_point,
    nearest_on_polyline,
    split_control_points,
    split_polyline,
)

INSERT_MODES = ("append", "prepend", "nearest")
#: How the insert modes read in the UI ("New points: at the end").
INSERT_MODE_LABELS = {"append": "at the end", "prepend": "at the start", "nearest": "between nearest"}

#: Undo steps kept per session.
MAX_HISTORY = 200

#: Restorable editing state: (filaments, pending control points, active ID).
_State = Tuple[Dict[int, Any], Dict[int, np.ndarray], int]


class FilamentEditSession:
    """Traced filaments being edited.

    Args:
        run: The copick run.
        object_name: Pickable object (should be a filament object).
        user_id, session_id: Identity of the filament set.
        step: Arc-length spacing of the regenerated points, in Angstrom (usually the tomogram voxel spacing).
        source: The ``CopickFilaments`` the session was opened from, if any.
    """

    def __init__(
        self,
        run: Any,
        object_name: str,
        user_id: str,
        session_id: str,
        step: float,
        source: Any = None,
    ):
        if step <= 0:
            raise ValueError("step must be positive")
        self.run = run
        self.object_name = object_name
        self.user_id = user_id
        self.session_id = session_id
        self.step = float(step)
        self.source = source
        self.filaments: Dict[int, Any] = {}  # instance_id -> CopickFilament (>= 2 control points)
        self.pending: Dict[int, np.ndarray] = {}  # instance_id -> control points of a filament with < 2 points
        self._handles: Dict[int, Tuple[np.ndarray, str, bool]] = {}
        self.active_id: int = 1
        self.insert_mode: str = "append"
        self.dirty = False
        # Undo history: (label, state before the step) / (label, state after undoing it).
        self._undo: List[Tuple[str, _State]] = []
        self._redo: List[Tuple[str, _State]] = []
        self._step_depth = 0
        self._step_label = ""
        self._step_state: Optional[_State] = None
        self._step_changed = False
        #: Called with the step's label whenever a new undo step is recorded.
        self.on_history: Optional[Callable[[str], None]] = None
        if source is not None:
            for f in source.filaments:
                self.filaments[int(f.instance_id)] = f
            self.active_id = self.next_id() if not self.filaments else min(self.filaments)

    # ------------------------------------------------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------------------------------------------------

    @classmethod
    def from_filaments(cls, copick_filaments: Any, step: Optional[float] = None) -> "FilamentEditSession":
        """Open an existing ``CopickFilaments`` for editing (step defaults to the file's voxel spacing)."""
        step = step or copick_filaments.voxel_spacing
        if not step:
            raise ValueError("The filament set records no voxel spacing; pass step.")
        return cls(
            run=copick_filaments.run,
            object_name=copick_filaments.pickable_object_name,
            user_id=copick_filaments.user_id,
            session_id=copick_filaments.session_id,
            step=step,
            source=copick_filaments,
        )

    @property
    def read_only(self) -> bool:
        """Tool output (session 0) and read-only backends are not edited in place."""
        if str(self.session_id) == "0":
            return True
        return bool(getattr(self.source, "read_only", False))

    @property
    def object(self) -> Any:
        return self.run.root.get_object(self.object_name)

    @property
    def radius(self) -> Optional[float]:
        obj = self.object
        return getattr(obj, "radius", None) if obj is not None else None

    # ------------------------------------------------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------------------------------------------------

    def ids(self) -> List[int]:
        return sorted(set(self.filaments) | set(self.pending))

    def next_id(self) -> int:
        ids = self.ids()
        return (max(ids) + 1) if ids else 1

    def controls(self, instance_id: int) -> np.ndarray:
        """(n, 3) control points of one filament (Angstrom, [x, y, z])."""
        if instance_id in self.pending:
            return self.pending[instance_id].copy()
        if instance_id not in self.filaments:
            return np.zeros((0, 3))
        return self._handle(instance_id)[0].copy()

    def kind(self, instance_id: int) -> Optional[str]:
        if instance_id in self.pending:
            return "catmull-rom"
        if instance_id not in self.filaments:
            return None
        return self._handle(instance_id)[1]

    def can_add_remove(self, instance_id: int) -> bool:
        """False for a B-spline (its knots fix the number of control points)."""
        if instance_id not in self.filaments:
            return True
        return self._handle(instance_id)[2]

    def polylines(self) -> Dict[int, np.ndarray]:
        """Regenerated centrelines, ``{id: (M, 3)}`` in Angstrom."""
        return {i: np.asarray(f.points, dtype=float) for i, f in sorted(self.filaments.items())}

    def all_controls(self) -> Dict[int, np.ndarray]:
        return {i: self.controls(i) for i in self.ids()}

    def _handle(self, instance_id: int) -> Tuple[np.ndarray, str, bool]:
        if instance_id not in self._handles:
            self._handles[instance_id] = editable_handles(self.filaments[instance_id])
        return self._handles[instance_id]

    # ------------------------------------------------------------------------------------------------------------
    # Undo / redo
    # ------------------------------------------------------------------------------------------------------------

    def _state(self) -> _State:
        # CopickFilament models are replaced, never mutated, so a shallow copy of the dict is enough.
        return dict(self.filaments), {i: cps.copy() for i, cps in self.pending.items()}, self.active_id

    def _restore(self, state: _State) -> None:
        filaments, pending, active_id = state
        self.filaments = dict(filaments)
        self.pending = {i: cps.copy() for i, cps in pending.items()}
        self.active_id = active_id
        self._handles.clear()
        self.dirty = True

    def _changed(self) -> None:
        self.dirty = True
        self._step_changed = True

    def begin_step(self, label: str) -> None:
        """Start an undo step; edits until the matching ``end_step()`` undo together. Steps nest into the outermost."""
        if self._step_depth == 0:
            self._step_label = label
            self._step_state = self._state()
            self._step_changed = False
        self._step_depth += 1

    def end_step(self) -> None:
        """Finish an undo step; it is recorded only if something changed."""
        if self._step_depth == 0:
            return
        self._step_depth -= 1
        if self._step_depth or not self._step_changed or self._step_state is None:
            return
        self._undo.append((self._step_label, self._step_state))
        del self._undo[:-MAX_HISTORY]
        self._redo.clear()
        self._step_state = None
        if self.on_history is not None:
            self.on_history(self._step_label)

    @contextmanager
    def history_step(self, label: str) -> Iterator[None]:
        """``with session.history_step("Move point"): ...`` groups the edits inside into one undo step."""
        self.begin_step(label)
        try:
            yield
        finally:
            self.end_step()

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    def undo(self) -> Optional[str]:
        """Undo the last step; returns its label, or None if there is nothing to undo."""
        if not self._undo:
            return None
        label, state = self._undo.pop()
        self._redo.append((label, self._state()))
        self._restore(state)
        return label

    def redo(self) -> Optional[str]:
        """Redo the last undone step; returns its label, or None if there is nothing to redo."""
        if not self._redo:
            return None
        label, state = self._redo.pop()
        self._undo.append((label, self._state()))
        self._restore(state)
        return label

    # ------------------------------------------------------------------------------------------------------------
    # Edits (each regenerates the affected filament through copick core and is one undo step)
    # ------------------------------------------------------------------------------------------------------------

    def set_controls(self, instance_id: int, control_points: Sequence[Sequence[float]]) -> None:
        """Replace the control points of one filament (creating it if new). Fewer than two points keep it pending."""
        cps = np.asarray(control_points, dtype=float).reshape(-1, 3)
        instance_id = int(instance_id)
        with self.history_step("Edit filament"):
            self._set_controls(instance_id, cps)

    def _set_controls(self, instance_id: int, cps: np.ndarray) -> None:
        from copick.models import CopickFilament

        self._handles.pop(instance_id, None)
        if len(cps) == 0:
            self.filaments.pop(instance_id, None)
            self.pending.pop(instance_id, None)
        elif len(cps) < 2:
            self.filaments.pop(instance_id, None)
            self.pending[instance_id] = cps
        elif instance_id in self.filaments:
            # keep the curve's own step (and kind); new filaments use the session step
            self.filaments[instance_id] = self.filaments[instance_id].with_control_points(cps)
        else:
            self.pending.pop(instance_id, None)
            self.filaments[instance_id] = CopickFilament.from_control_points(
                instance_id,
                cps,
                step=self.step,
                radius=self.radius,
            )
        self._changed()

    def insert_point(
        self,
        point: Sequence[float],
        instance_id: Optional[int] = None,
        mode: Optional[str] = None,
    ) -> int:
        """Insert a control point into a filament (default: the active one, by the session's insert mode).

        Returns:
            The index of the new point within the filament's control points.

        Raises:
            ValueError: If the filament's curve is a B-spline (fixed number of points).
        """
        instance_id = self.active_id if instance_id is None else int(instance_id)
        if not self.can_add_remove(instance_id):
            raise ValueError(
                f"Filament {instance_id} is a B-spline fit; convert it to Catmull-Rom to add or remove points.",
            )
        cps, index = insert_control_point(self.controls(instance_id), point, mode or self.insert_mode)
        with self.history_step("Add filament point"):
            self.set_controls(instance_id, cps)
        return index

    def move_point(self, instance_id: int, index: int, point: Sequence[float]) -> None:
        cps = self.controls(instance_id)
        cps[index] = np.asarray(point, dtype=float)
        with self.history_step("Move filament point"):
            self.set_controls(instance_id, cps)

    def remove_point(self, instance_id: int, index: int) -> None:
        if not self.can_add_remove(instance_id):
            raise ValueError(
                f"Filament {instance_id} is a B-spline fit; convert it to Catmull-Rom to add or remove points.",
            )
        cps = self.controls(instance_id)
        with self.history_step("Delete filament point"):
            self.set_controls(instance_id, np.delete(cps, index, axis=0))

    def new_filament(self) -> int:
        """Start a new (empty) filament and make it active."""
        next_id = self.next_id()
        if next_id != self.active_id:  # already on an empty new filament: nothing to undo
            with self.history_step("New filament"):
                self.active_id = next_id
                self._step_changed = True
        return self.active_id

    def delete_filament(self, instance_id: int) -> None:
        if int(instance_id) not in self.filaments and int(instance_id) not in self.pending:
            return
        with self.history_step("Delete filament"):
            before = self.ids()
            self.filaments.pop(int(instance_id), None)
            self.pending.pop(int(instance_id), None)
            self._handles.pop(int(instance_id), None)
            if self.active_id == instance_id:  # stay in place: the next filament, or the previous at the end
                ids = self.ids()
                k = before.index(int(instance_id)) if int(instance_id) in before else 0
                self.active_id = ids[min(k, len(ids) - 1)] if ids else 1
            self._changed()

    def reverse(self, instance_id: int) -> None:
        instance_id = int(instance_id)
        with self.history_step("Reverse filament"):
            if instance_id in self.filaments:
                self.filaments[instance_id] = self.filaments[instance_id].reversed()
            elif instance_id in self.pending:
                self.pending[instance_id] = self.pending[instance_id][::-1].copy()
            else:
                return
            self._handles.pop(instance_id, None)
            self._changed()

    def convert_to_catmull_rom(self, instance_id: int) -> None:
        """Make a B-spline (or any curve) editable with add/remove: derive Catmull-Rom handles from its points."""
        from copick.models import CopickFilament

        f = self.filaments[int(instance_id)]
        curve = f.editable_curve(kinds=("catmull-rom",))
        fields = f.model_dump(exclude={"instance_id", "points", "curve"})
        with self.history_step("Convert filament to Catmull-Rom"):
            self.filaments[int(instance_id)] = CopickFilament.from_curve(int(instance_id), curve, **fields)
            self._handles.pop(int(instance_id), None)
            self._changed()

    def nearest_filament(self, point: Sequence[float]) -> Optional[Tuple[int, float]]:
        """The filament whose centreline passes closest to ``point``: ``(instance_id, distance)``, or None."""
        best = None
        for instance_id, f in self.filaments.items():
            line = np.asarray(f.points, dtype=float)
            if len(line) < 2:
                continue
            dist = nearest_on_polyline(line, point)[2]
            if best is None or dist < best[1]:
                best = (instance_id, dist)
        return best

    def cut(
        self,
        point: Sequence[float],
        instance_id: Optional[int] = None,
        tolerance: Optional[float] = None,
    ) -> Tuple[int, int]:
        """Cut a filament in two where its centreline passes closest to ``point`` (one undo step).

        The first piece keeps the filament's ID, the second gets the next free ID; both keep the filament's other
        fields (polarity, score, radius, metadata). Catmull-Rom and linear filaments are split at their control points
        with the cut point added to both pieces, so their handles stay where they were. Other curves (B-spline fits)
        are split along their centreline and get Catmull-Rom handles derived from each piece.

        Args:
            point: Where to cut (Angstrom).
            instance_id: The filament to cut; default the one passing closest to ``point``.
            tolerance: Largest distance of ``point`` from the centreline.

        Returns:
            The IDs of the two pieces, in order along the original filament.

        Raises:
            ValueError: If no filament is close enough, or the cut is too close to an end.
        """
        from copick.models import CopickFilament
        from copick.util.filaments import control_points_from_polyline

        if instance_id is None:
            nearest = self.nearest_filament(point)
            if nearest is None:
                raise ValueError("There is no filament to cut.")
            instance_id = nearest[0]
        instance_id = int(instance_id)
        if instance_id not in self.filaments:
            raise ValueError(f"Filament {instance_id} has fewer than two control points; there is nothing to cut.")
        f = self.filaments[instance_id]
        line = np.asarray(f.points, dtype=float)
        distance = nearest_on_polyline(line, point)[2]
        if tolerance is not None and distance > tolerance:
            raise ValueError(f"No filament within {tolerance:g} Å of the click.")
        curve = f.curve if f.curve_is_current() else None
        step = float(curve.step) if curve is not None else self.step
        min_gap = step
        if self.can_add_remove(instance_id):
            kind = self.kind(instance_id) if self.kind(instance_id) in ("catmull-rom", "linear") else "catmull-rom"
            pieces = split_control_points(self.controls(instance_id), line, point, min_gap)
        else:
            kind = "catmull-rom"
            pieces = tuple(
                control_points_from_polyline(piece, tolerance=step / 2)
                for piece in split_polyline(line, point, min_gap)
            )
        alpha = curve.alpha if curve is not None and curve.alpha is not None else 0.5
        fields = f.model_dump(exclude={"instance_id", "points", "curve"})
        new_id = self.next_id()
        if new_id == self.active_id:  # the active filament is a new, still empty one: keep its ID for it
            new_id += 1
        with self.history_step("Cut filament"):
            for piece_id, cps in zip((instance_id, new_id), pieces):
                self.filaments[piece_id] = CopickFilament.from_control_points(
                    piece_id,
                    cps,
                    step=step,
                    kind=kind,
                    alpha=alpha,
                    **fields,
                )
                self._handles.pop(piece_id, None)
            self.pending.pop(new_id, None)
            self._changed()
        return instance_id, new_id

    def _join_handles(self, instance_id: int) -> np.ndarray:
        """Control points to join with: the filament's own (Catmull-Rom, linear) or Catmull-Rom handles derived from
        it (B-spline fits, filaments without a curve)."""
        if self.kind(instance_id) in ("catmull-rom", "linear"):
            return self.controls(instance_id)
        curve = self.filaments[instance_id].editable_curve(kinds=("catmull-rom",))
        return np.asarray(curve.control_points, dtype=float)

    def join(self, instance_ids: Sequence[int], target: Optional[int] = None) -> int:
        """Join filaments end to end into one (one undo step).

        Starting from ``target`` (default: the first of ``instance_ids``), the filament whose end is nearest to either
        end of the chain is attached there, reversed if needed, until all are joined; the target keeps its direction,
        ID and fields (polarity, score, radius, metadata), the others are removed. The joined curve is Catmull-Rom
        (linear if every part is linear) through all control points.

        Returns:
            The ID of the joined filament.

        Raises:
            ValueError: If fewer than two of ``instance_ids`` are complete filaments.
        """
        from copick.models import CopickFilament

        ids = [i for i in dict.fromkeys(int(i) for i in instance_ids) if i in self.filaments]
        if len(ids) < 2:
            raise ValueError("Select at least two filaments to join.")
        target = int(target) if target is not None and int(target) in ids else ids[0]
        kinds = {self.kind(i) for i in ids}
        kind = "linear" if kinds == {"linear"} else "catmull-rom"
        f = self.filaments[target]
        curve = f.curve if f.curve_is_current() else None
        step = float(curve.step) if curve is not None else self.step
        alpha = curve.alpha if curve is not None and curve.alpha is not None else 0.5
        chain = self._join_handles(target)
        remaining = {i: self._join_handles(i) for i in ids if i != target}
        while remaining:
            # (distance, id, attach at the end?, reverse the part?)
            options = []
            for i, cps in remaining.items():
                options += [
                    (np.linalg.norm(chain[-1] - cps[0]), i, True, False),
                    (np.linalg.norm(chain[-1] - cps[-1]), i, True, True),
                    (np.linalg.norm(chain[0] - cps[-1]), i, False, False),
                    (np.linalg.norm(chain[0] - cps[0]), i, False, True),
                ]
            dist, i, at_end, flip = min(options, key=lambda o: o[0])
            part = remaining.pop(i)[::-1] if flip else remaining.pop(i)
            if at_end:
                if dist < step / 2:  # touching ends: keep one point
                    part = part[1:]
                chain = np.vstack([chain, part])
            else:
                if dist < step / 2:
                    part = part[:-1]
                chain = np.vstack([part, chain])
        fields = f.model_dump(exclude={"instance_id", "points", "curve"})
        with self.history_step("Join filaments"):
            for i in ids:
                if i != target:
                    self.filaments.pop(i, None)
                    self.pending.pop(i, None)
                    self._handles.pop(i, None)
            self.filaments[target] = CopickFilament.from_control_points(
                target,
                chain,
                step=step,
                kind=kind,
                alpha=alpha,
                **fields,
            )
            self._handles.pop(target, None)
            self.active_id = target
            self._changed()
        return target

    def set_polarity_known(self, instance_id: int, known: bool) -> None:
        f = self.filaments[int(instance_id)]
        with self.history_step("Set filament polarity"):
            self.filaments[int(instance_id)] = f.model_copy(update={"polarity_known": bool(known)})
            self._changed()

    # ------------------------------------------------------------------------------------------------------------
    # Saving
    # ------------------------------------------------------------------------------------------------------------

    def to_list(self) -> List[Any]:
        """The complete filaments (pending ones with < 2 points are left out), in ID order."""
        return [self.filaments[i] for i in sorted(self.filaments)]

    def save(
        self,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        voxel_spacing: Optional[float] = None,
        pick_spacing: Optional[float] = None,
        exist_ok: bool = True,
    ) -> Dict[str, Any]:
        """Store the filaments (and optionally picks sampled along them, which replace the whole picks set of the same
        object / user / session).

        Returns:
            ``{"filaments": CopickFilaments, "picks": CopickPicks or None, "n_filaments": int, "n_picks": int}``.
        """
        user_id = user_id or self.user_id
        session_id = session_id or self.session_id
        filaments = self.to_list()
        target = self.run.new_filaments(self.object_name, session_id=session_id, user_id=user_id, exist_ok=exist_ok)
        target.filaments = filaments
        target.meta.voxel_spacing = voxel_spacing if voxel_spacing is not None else self.step
        target.store()
        result = {"filaments": target, "picks": None, "n_filaments": len(filaments), "n_picks": 0}
        if pick_spacing:
            positions, transforms, ids, scores = filaments_to_picks(filaments, pick_spacing)
            picks = self.run.new_picks(self.object_name, session_id=session_id, user_id=user_id, exist_ok=True)
            picks.from_numpy(positions, transforms, instance_ids=ids, scores=scores)
            result["picks"] = picks
            result["n_picks"] = len(positions)
        self.user_id, self.session_id, self.source = user_id, session_id, target
        self.dirty = False
        return result
