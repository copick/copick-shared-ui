"""A compact table of instances (filaments, pick groups, instance or panoptic segments) with stepping, focus,
visibility and simple edit actions. Host applications fill it with ``InstanceRow``s and react to its signals; it
never touches copick data itself.

Each instance is one two-line row (``CompactItemDelegate``): swatch and title (``#12``, ``ribosome #3``), and a
caption with its numbers (``245 pts · score 0.93``, ``1.42 µm · catmull-rom``, ``12,345 voxels``). The header is a
"sort by" menu (ID, count, length, score, label)."""

from typing import Callable, Iterable, List, Optional, Set

from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QBrush, QColor
from qtpy.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from copick_shared_ui.util.instances import (
    InstanceRow,
    format_id_set,
    format_length,
    instance_row_caption,
    instance_row_title,
    parse_id_set,
)
from copick_shared_ui.widgets.compact_delegate import (
    CAPTION_ROLE,
    SWATCH_ROLE,
    CompactItemDelegate,
    SortMenu,
    make_compact,
)
from copick_shared_ui.widgets.flow_layout import FlowLayout

_COLUMNS = ["", "Instances"]
_COL_VISIBLE, _COL_MAIN = range(len(_COLUMNS))
_KEY_ROLE = Qt.UserRole + 1  # the row key (instance ID, or segment index for panoptic rows)
_ID_ROLE = Qt.UserRole + 2  # the instance ID

#: Sort keys of the header menu: (key, menu text, InstanceRow attribute).
_SORT_KEYS = (
    ("id", "ID", "instance_id"),
    ("count", "Count", "count"),
    ("length", "Length", "length"),
    ("score", "Score", "score"),
    ("label", "Label", "label"),
)


class InstanceBrowserWidget(QWidget):
    """Browse and act on the instances of one entity.

    Signals carry row keys (``InstanceRow.row_key``: the instance ID, or the segment index for panoptic rows).
    """

    current_changed = Signal(int)
    focus_requested = Signal(int)
    visibility_changed = Signal(object)  # set of visible row keys
    new_requested = Signal()
    delete_requested = Signal(object)  # list of row keys
    merge_requested = Signal(object, int)  # (source row keys, target row key)
    reverse_requested = Signal(int)
    color_by_instance_toggled = Signal(bool)
    selection_changed = Signal(object)  # list of selected row keys (user selection only, not set_selected_keys)

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        title: str = "Instances",
        button_factory: Optional[Callable[[str, str, Callable], QAbstractButton]] = None,
    ):
        """``button_factory(text, tooltip, slot)`` makes the action buttons, so a host can match its own buttons
        (default: flat tool buttons)."""
        super().__init__(parent)
        self._button_factory = button_factory
        self._rows: List[InstanceRow] = []
        self._kind = ""
        self._title = title
        self._updating = False
        self._setup_ui()
        self.set_capabilities()
        self._update_header()

    # ------------------------------------------------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------------------------------------------------

    def _tool(self, text: str, tip: str, slot) -> QAbstractButton:
        if self._button_factory is not None:
            return self._button_factory(text, tip, slot)
        b = QToolButton()
        b.setText(text)
        b.setToolTip(tip)
        b.setAutoRaise(True)
        b.clicked.connect(slot)
        return b

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        head = QWidget()
        head_layout = FlowLayout(head, h_spacing=8)
        self._header = QLabel()
        head_layout.addWidget(self._header)
        self._color_cb = QCheckBox("Colour by instance")
        self._color_cb.setChecked(True)
        self._color_cb.toggled.connect(self.color_by_instance_toggled)
        head_layout.addWidget(self._color_cb)
        layout.addWidget(head)

        self._filter = QLineEdit()
        self._filter.setPlaceholderText("Filter: IDs (e.g. 1-5, 9) or text")
        self._filter.setClearButtonEnabled(True)
        self._filter.textChanged.connect(self._apply_filter)
        layout.addWidget(self._filter)

        self._table = QTableWidget(0, len(_COLUMNS))
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSortingEnabled(False)  # rows are filled in the order of the sort menu
        self._table.setAlternatingRowColors(False)
        make_compact(self._table, CompactItemDelegate(self._table, inline=True), column=_COL_MAIN)
        self._table.horizontalHeader().setSectionResizeMode(_COL_VISIBLE, QHeaderView.ResizeToContents)
        self._table.setMinimumHeight(60)
        self._sort = SortMenu(
            self._table.horizontalHeader(),
            "Instances",
            [(k, t) for k, t, _a in _SORT_KEYS],
            lambda _key, _desc: self._refill(),
            column=_COL_MAIN,
        )
        self._table.itemChanged.connect(self._on_item_changed)
        self._table.currentCellChanged.connect(self._on_current_cell_changed)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        self._table.cellDoubleClicked.connect(lambda r, _c: self._emit_focus_row(r))
        layout.addWidget(self._table, 1)

        bar_widget = QWidget()
        bar = FlowLayout(bar_widget, h_spacing=2, v_spacing=2, center=True)
        self._prev_btn = self._tool("◀", "Previous instance", lambda: self.step(-1))
        self._next_btn = self._tool("▶", "Next instance", lambda: self.step(1))
        self._focus_btn = self._tool("🎯", "Focus the current instance", self._on_focus)
        self._show_all_btn = self._tool("👁", "Show all instances", self.show_all)
        self._isolate_btn = self._tool("◎", "Show only the selected instances", self._on_isolate)
        self._hide_btn = self._tool("🚫", "Hide the selected instances", self._on_hide)
        self._new_btn = self._tool("＋", "New instance ID", self.new_requested.emit)
        self._delete_btn = self._tool("🗑", "Delete the selected instances", self._on_delete)
        self._merge_btn = self._tool("⧉", "Merge the selected instances into the current one", self._on_merge)
        self._reverse_btn = self._tool("⇄", "Reverse the current filament", self._on_reverse)
        for b in (
            self._prev_btn,
            self._next_btn,
            self._focus_btn,
            self._show_all_btn,
            self._isolate_btn,
            self._hide_btn,
            self._new_btn,
            self._merge_btn,
            self._reverse_btn,
            self._delete_btn,
        ):
            bar.addWidget(b)
        layout.addWidget(bar_widget)

    # ------------------------------------------------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------------------------------------------------

    def set_title(self, title: str) -> None:
        self._title = title
        self._update_header()

    def set_capabilities(
        self,
        new: bool = False,
        delete: bool = False,
        merge: bool = False,
        reverse: bool = False,
        color_toggle: bool = False,
        merge_tip: Optional[str] = None,
    ) -> None:
        """Show only the actions the current entity supports (``merge_tip`` renames the merge action, e.g. "Join the
        selected filaments end to end")."""
        self._new_btn.setVisible(new)
        self._delete_btn.setVisible(delete)
        self._merge_btn.setVisible(merge)
        self._merge_btn.setToolTip(merge_tip or "Merge the selected instances into the current one")
        self._reverse_btn.setVisible(reverse)
        self._color_cb.setVisible(color_toggle)

    def set_color_by_instance(self, on: bool) -> None:
        self._color_cb.blockSignals(True)
        self._color_cb.setChecked(on)
        self._color_cb.blockSignals(False)

    def set_rows(self, rows: Iterable[InstanceRow], kind: str = "") -> None:
        """Replace the rows, keeping the current row and the visibility of rows that stay."""
        previous_current = self.current_key()
        hidden = {r.row_key for r in self._rows if not r.visible}
        self._rows = list(rows)
        for r in self._rows:
            if r.row_key in hidden:
                r.visible = False
        self._kind = kind
        # Offer only the sort keys some row has (no lengths for picks, no scores for segmentations, ...).
        self._sort.set_options(
            [(k, t) for k, t, a in _SORT_KEYS if k == "id" or any(getattr(r, a) not in (None, "") for r in self._rows)],
        )
        self._refill(previous_current)
        self._update_header()

    def set_sort(self, key: str, descending: bool = False) -> None:
        """Sort by ``id``, ``count``, ``length``, ``score`` or ``label`` (what the header menu does)."""
        self._sort.select(key, descending)

    def _sorted_rows(self) -> List[InstanceRow]:
        attr = {k: a for k, _t, a in _SORT_KEYS}.get(self._sort.key, "instance_id")

        def key(r: InstanceRow):
            v = getattr(r, attr)
            missing = v is None or v == ""
            return (missing, v if not missing else 0, r.instance_id, r.row_key)

        rows = sorted(self._rows, key=key, reverse=self._sort.descending)
        if self._sort.descending:  # keep rows without a value last
            rows = [r for r in rows if not key(r)[0]] + [r for r in rows if key(r)[0]]
        return rows

    def _refill(self, keep_current: Optional[int] = None) -> None:
        """Fill the table in sort order, keeping the current row."""
        current = self.current_key() if keep_current is None else keep_current
        self._updating = True
        rows = self._sorted_rows()
        self._table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            self._fill_row(i, row)
        self._updating = False
        self._apply_filter()
        if current is not None:
            self.set_current(current, emit=False)

    def clear(self) -> None:
        self.set_rows([], "")

    def rows(self) -> List[InstanceRow]:
        return list(self._rows)

    def current_key(self) -> Optional[int]:
        r = self._table.currentRow()
        if r < 0:
            return None
        item = self._table.item(r, _COL_MAIN)
        return None if item is None else int(item.data(_KEY_ROLE))

    def selected_keys(self) -> List[int]:
        keys = []
        for index in self._table.selectionModel().selectedRows(_COL_MAIN):
            item = self._table.item(index.row(), _COL_MAIN)
            if item is not None:
                keys.append(int(item.data(_KEY_ROLE)))
        return keys

    def set_selected_keys(self, keys: Iterable[int], emit: bool = False) -> None:
        """Select the rows of ``keys`` (e.g. to mirror a selection made in the 3D view)."""
        keys = {int(k) for k in keys}
        if set(self.selected_keys()) == keys:
            return
        updating, self._updating = self._updating, not emit
        selection = self._table.selectionModel()
        selection.clearSelection()
        model = self._table.model()
        for k in keys:
            row = self._table_row_of(k)
            if row is not None:
                selection.select(model.index(row, _COL_MAIN), selection.Select | selection.Rows)
        self._updating = updating
        if emit:
            self.selection_changed.emit(self.selected_keys())

    def visible_keys(self) -> Set[int]:
        return {r.row_key for r in self._rows if r.visible}

    def set_current(self, key: int, emit: bool = True) -> None:
        row = self._table_row_of(key)
        if row is None:
            return
        if not emit:
            self._updating = True
        self._table.setCurrentCell(row, _COL_MAIN)
        self._table.scrollToItem(self._table.item(row, _COL_MAIN))
        self._updating = False

    def set_visible(self, keys: Iterable[int], emit: bool = True) -> None:
        keys = set(keys)
        for r in self._rows:
            r.visible = r.row_key in keys
        self._sync_checkboxes()
        if emit:
            self.visibility_changed.emit(self.visible_keys())

    def show_all(self) -> None:
        self.set_visible([r.row_key for r in self._rows])

    def step(self, delta: int) -> None:
        """Move to the next/previous visible, unfiltered row (in table order) and request focus on it."""
        candidates = [
            r for r in range(self._table.rowCount()) if not self._table.isRowHidden(r) and self._row_visible(r)
        ]
        if not candidates:
            return
        current = self._table.currentRow()
        if current in candidates:
            target = candidates[(candidates.index(current) + delta) % len(candidates)]
        elif current < 0:
            target = candidates[0] if delta > 0 else candidates[-1]
        elif delta > 0:  # the current row is hidden: continue from its position
            target = next((c for c in candidates if c > current), candidates[0])
        else:
            target = next((c for c in reversed(candidates) if c < current), candidates[-1])
        self._table.setCurrentCell(target, _COL_MAIN)
        self._emit_focus_row(target)

    # ------------------------------------------------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------------------------------------------------

    def _fill_row(self, i: int, row: InstanceRow) -> None:
        vis = QTableWidgetItem()
        vis.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable)
        vis.setCheckState(Qt.Checked if row.visible else Qt.Unchecked)
        vis.setToolTip("Show / hide")
        self._table.setItem(i, _COL_VISIBLE, vis)
        r, g, b, a = (float(c) for c in row.color[:4])
        tint = QBrush(QColor.fromRgbF(r, g, b, 0.2))  # the row carries the instance colour, as in the object tables
        vis.setBackground(tint)

        main = QTableWidgetItem(instance_row_title(row, self._kind))
        main.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        main.setData(_KEY_ROLE, int(row.row_key))
        main.setData(_ID_ROLE, int(row.instance_id))
        main.setData(CAPTION_ROLE, instance_row_caption(row, self._kind))
        main.setData(SWATCH_ROLE, QColor.fromRgbF(r, g, b, max(a, 0.2)))
        main.setBackground(tint)
        main.setToolTip(self._tooltip(row))
        self._table.setItem(i, _COL_MAIN, main)

    @staticmethod
    def _tooltip(row: InstanceRow) -> str:
        lines = [f"ID {row.instance_id}", f"count {row.count:,}"]
        if row.score is not None:
            lines.append(f"score {row.score:.3f}")
        if row.length is not None:
            lines.append(f"length {row.length:,.0f} Å ({format_length(row.length)})")
        if row.label:
            lines.append(row.label)
        return "\n".join(lines)

    def _table_row_of(self, key: int) -> Optional[int]:
        for r in range(self._table.rowCount()):
            item = self._table.item(r, _COL_MAIN)
            if item is not None and int(item.data(_KEY_ROLE)) == int(key):
                return r
        return None

    def _row_by_key(self, key: int) -> Optional[InstanceRow]:
        for r in self._rows:
            if r.row_key == key:
                return r
        return None

    def _row_visible(self, table_row: int) -> bool:
        item = self._table.item(table_row, _COL_VISIBLE)
        return item is not None and item.checkState() == Qt.Checked

    def _sync_checkboxes(self) -> None:
        self._updating = True
        for t in range(self._table.rowCount()):
            key = int(self._table.item(t, _COL_MAIN).data(_KEY_ROLE))
            row = self._row_by_key(key)
            if row is not None:
                self._table.item(t, _COL_VISIBLE).setCheckState(Qt.Checked if row.visible else Qt.Unchecked)
        self._updating = False
        self._update_header()

    def _apply_filter(self) -> None:
        text = self._filter.text().strip()
        ids: Optional[Set[int]] = None
        if text:
            try:
                ids = parse_id_set(text)
            except ValueError:
                ids = None
        for t in range(self._table.rowCount()):
            if not text:
                self._table.setRowHidden(t, False)
                continue
            item = self._table.item(t, _COL_MAIN)
            ident = int(item.data(_ID_ROLE))
            haystack = f"{item.text()} {item.data(CAPTION_ROLE) or ''}".lower()
            match = (ident in ids) if ids is not None else (text.lower() in haystack)
            self._table.setRowHidden(t, not match)

    def _update_header(self) -> None:
        n = len(self._rows)
        hidden = n - len(self.visible_keys())
        text = f"<b>{self._title}</b> — {n}"
        if hidden:
            text += f" ({hidden} hidden)"
        self._header.setText(text)
        hidden_ids = [r.instance_id for r in self._rows if not r.visible]
        self._header.setToolTip(f"Hidden: {format_id_set(hidden_ids)}" if hidden_ids else "")
        has_rows = n > 0
        for b in (self._prev_btn, self._next_btn, self._focus_btn, self._show_all_btn, self._isolate_btn):
            b.setEnabled(has_rows)

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._updating or item.column() != _COL_VISIBLE:
            return
        key = int(self._table.item(item.row(), _COL_MAIN).data(_KEY_ROLE))
        row = self._row_by_key(key)
        if row is None:
            return
        row.visible = item.checkState() == Qt.Checked
        self._update_header()
        self.visibility_changed.emit(self.visible_keys())

    def _on_selection_changed(self) -> None:
        if not self._updating:
            self.selection_changed.emit(self.selected_keys())

    def _on_current_cell_changed(self, row: int, _col: int, prev_row: int, _prev_col: int) -> None:
        if self._updating or row < 0 or row == prev_row:
            return
        item = self._table.item(row, _COL_MAIN)
        if item is not None:
            self.current_changed.emit(int(item.data(_KEY_ROLE)))

    def _emit_focus_row(self, table_row: int) -> None:
        item = self._table.item(table_row, _COL_MAIN)
        if item is not None:
            self.focus_requested.emit(int(item.data(_KEY_ROLE)))

    def _on_focus(self) -> None:
        key = self.current_key()
        if key is not None:
            self.focus_requested.emit(key)

    def _on_isolate(self) -> None:
        keys = self.selected_keys() or ([self.current_key()] if self.current_key() is not None else [])
        if keys:
            self.set_visible(keys)

    def _on_hide(self) -> None:
        keys = set(self.selected_keys())
        if keys:
            self.set_visible(self.visible_keys() - keys)

    def _on_delete(self) -> None:
        keys = self.selected_keys()
        if keys:
            self.delete_requested.emit(keys)

    def _on_merge(self) -> None:
        keys = self.selected_keys()
        target = self.current_key()
        if len(keys) < 2:
            return
        if target not in keys:
            target = min(keys)
        self.merge_requested.emit([k for k in keys if k != target], target)

    def _on_reverse(self) -> None:
        key = self.current_key()
        if key is not None:
            self.reverse_requested.emit(key)
