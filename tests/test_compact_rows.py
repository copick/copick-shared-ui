"""Compact two-line rows: the delegate, the sort menu, the instance browser and its title/caption helpers."""

import pytest

from copick_shared_ui.util.instances import InstanceRow, format_length, instance_row_caption, instance_row_title


def test_titles_and_captions_per_kind():
    assert instance_row_title(InstanceRow(12, count=245, score=0.934), "picks") == "#12"
    assert instance_row_caption(InstanceRow(12, count=245, score=0.934), "picks") == "245 pts · score 0.93"
    assert instance_row_title(InstanceRow(0, count=3, label="unassigned"), "picks") == "unassigned"
    assert instance_row_caption(InstanceRow(0, count=1, label="unassigned"), "picks") == "1 pt"

    fil = InstanceRow(3, count=900, score=1.0, length=14_210.0, label="catmull-rom")
    assert instance_row_caption(fil, "filaments") == "1.42 µm · score 1.00 · catmull-rom"
    assert instance_row_caption(InstanceRow(4, count=1, label="pending"), "filaments") == "pending · 1 control point"

    assert instance_row_caption(InstanceRow(7, count=12345, label="ribosome"), "instance") == "12,345 voxels"
    assert instance_row_title(InstanceRow(3, count=10, label="virion", key=5), "panoptic") == "virion #3"
    assert instance_row_title(InstanceRow(0, count=10, label="membrane", key=6), "panoptic") == "membrane (stuff)"

    assert format_length(8420.0) == "842 nm" and format_length(None) == ""


def test_delegate_size_and_paint(qtbot):
    from qtpy.QtCore import QRect, Qt
    from qtpy.QtGui import QColor, QFontMetrics, QImage, QPainter
    from qtpy.QtWidgets import QStyleOptionViewItem, QTableWidget, QTableWidgetItem

    from copick_shared_ui.widgets.compact_delegate import (
        CAPTION_ROLE,
        CHIP_ROLE,
        MULTI_SWATCH,
        SWATCH_ROLE,
        CompactItemDelegate,
        make_compact,
    )

    table = QTableWidget(2, 1)
    qtbot.addWidget(table)
    delegate = make_compact(table)
    for row, swatch in ((0, QColor("red")), (1, MULTI_SWATCH)):
        item = QTableWidgetItem("a-very-long-object-name-that-does-not-fit " * 3)
        item.setData(CAPTION_ROLE, "data-portal · 237075 · 6.13 Å")
        item.setData(CHIP_ROLE, "inst")
        item.setData(SWATCH_ROLE, swatch)
        table.setItem(row, 0, item)

    fm = QFontMetrics(table.font())
    h = delegate.row_height(table.font())
    assert h > 2 * fm.height() * 0.85 and table.rowHeight(0) == h  # two lines, applied to the view
    option = QStyleOptionViewItem()
    option.font = table.font()
    assert delegate.sizeHint(option, table.model().index(0, 0)).width() <= 80  # never forces the column wide

    image = QImage(220, h, QImage.Format_ARGB32)
    image.fill(Qt.white)
    painter = QPainter(image)
    option.rect = QRect(0, 0, 220, h)
    option.palette = table.palette()
    for row in (0, 1):
        CompactItemDelegate().paint(painter, option, table.model().index(row, 0))
    painter.end()
    assert any(image.pixelColor(x, h // 4) != QColor(Qt.white) for x in range(0, 220, 3))  # something was drawn


def test_sort_menu_labels_and_selects(qtbot):
    from qtpy.QtCore import Qt
    from qtpy.QtWidgets import QTableWidget

    from copick_shared_ui.widgets.compact_delegate import SortMenu, make_compact

    table = QTableWidget(0, 1)
    qtbot.addWidget(table)
    make_compact(table)
    chosen = []
    menu = SortMenu(
        table.horizontalHeader(),
        "Object",
        [("default", "Default"), ("user", "User")],
        lambda k, d: chosen.append((k, d)),
    )
    assert menu.text == "Object ▾"
    menu.select("user")
    assert chosen[-1] == ("user", False) and "by user" in menu.text
    assert table.model().headerData(0, Qt.Horizontal) == menu.text
    actions = [a.text() for a in menu.menu().actions() if a.text()]
    assert actions == ["Default", "User", "Descending"]
    menu.select("user", True)
    assert chosen[-1] == ("user", True) and menu.text.endswith("↓")


@pytest.fixture
def browser(qtbot):
    from copick_shared_ui.widgets.instances import InstanceBrowserWidget

    w = InstanceBrowserWidget(title="Pick instances")
    qtbot.addWidget(w)
    rows = [
        InstanceRow(1, count=30, score=0.5),
        InstanceRow(2, count=10, score=0.9),
        InstanceRow(3, count=20, score=None),
        InstanceRow(0, count=5, label="unassigned"),
    ]
    w.set_rows(rows, kind="picks")
    return w


def _order(w):
    from copick_shared_ui.widgets.instances.instance_browser import _COL_MAIN, _KEY_ROLE

    return [int(w._table.item(r, _COL_MAIN).data(_KEY_ROLE)) for r in range(w._table.rowCount())]


def test_browser_is_two_columns_with_captions(browser):
    from copick_shared_ui.widgets.compact_delegate import CAPTION_ROLE
    from copick_shared_ui.widgets.instances.instance_browser import _COL_MAIN

    assert browser._table.columnCount() == 2
    first = browser._table.item(0, _COL_MAIN)
    assert first.text() == "unassigned" and first.data(CAPTION_ROLE) == "5 pts"
    assert browser._table.item(1, _COL_MAIN).data(CAPTION_ROLE) == "30 pts · score 0.50"
    # sort keys are offered only when some row has them: no lengths for picks
    keys = [a.text() for a in browser._sort.menu().actions() if a.text()]
    assert keys == ["ID", "Count", "Score", "Label", "Descending"]


def test_browser_sort_menu_orders_rows_and_stepping(browser):
    assert _order(browser) == [0, 1, 2, 3]
    browser.set_sort("count", descending=True)
    assert _order(browser) == [1, 3, 2, 0]
    browser.set_sort("score", descending=True)
    assert _order(browser) == [2, 1, 3, 0]  # rows without a score last
    seen = []
    browser.focus_requested.connect(seen.append)
    browser.set_current(2, emit=False)
    browser.step(1)
    assert seen == [1]  # stepping follows the sorted order
    # a refresh keeps the order and the current row
    rows = [InstanceRow(i, count=c, score=s) for i, c, s in ((1, 30, 0.5), (2, 10, 0.9), (3, 20, None))]
    browser.set_rows(rows, kind="picks")
    assert _order(browser)[:2] == [2, 1] and browser.current_key() == 1


def test_browser_filter_matches_ids_and_caption_text(browser):
    from copick_shared_ui.widgets.instances.instance_browser import _COL_MAIN, _KEY_ROLE

    def shown():
        t = browser._table
        return sorted(int(t.item(r, _COL_MAIN).data(_KEY_ROLE)) for r in range(t.rowCount()) if not t.isRowHidden(r))

    browser._filter.setText("1-2")
    assert shown() == [1, 2]
    browser._filter.setText("score 0.9")
    assert shown() == [2]
    browser._filter.setText("unassigned")
    assert shown() == [0]


def test_browser_panoptic_titles(qtbot):
    from copick_shared_ui.widgets.instances import InstanceBrowserWidget
    from copick_shared_ui.widgets.instances.instance_browser import _COL_MAIN

    w = InstanceBrowserWidget(title="Panoptic segments")
    qtbot.addWidget(w)
    w.set_rows(
        [InstanceRow(0, count=100, label="membrane", key=1), InstanceRow(2, count=40, label="virion", key=2)],
        kind="panoptic",
    )
    assert {w._table.item(r, _COL_MAIN).text() for r in range(2)} == {"membrane (stuff)", "virion #2"}
    w.set_current(2, emit=False)
    assert w.current_key() == 2


def test_arrow_keys_wrap_around(qtbot, browser):
    from qtpy.QtCore import Qt

    from copick_shared_ui.widgets.instances.instance_browser import _COL_MAIN

    table = browser._table
    table.setFocus()
    table.setCurrentCell(0, _COL_MAIN)
    qtbot.keyClick(table, Qt.Key_Up)
    assert table.currentRow() == table.rowCount() - 1  # up on the first row wraps to the last
    qtbot.keyClick(table, Qt.Key_Down)
    assert table.currentRow() == 0  # down on the last wraps to the first
    qtbot.keyClick(table, Qt.Key_Down)
    assert table.currentRow() == 1  # in between, the normal move
    browser._filter.setText("1-2")  # rows 0 (unassigned) and 3 hidden
    table.setCurrentCell(2, _COL_MAIN)
    qtbot.keyClick(table, Qt.Key_Down)
    assert table.currentRow() == 1  # wraps to the first shown row


def test_browser_selection_signal_and_mirroring(browser):
    seen = []
    browser.selection_changed.connect(seen.append)
    browser.set_selected_keys([1, 3])  # mirrored from elsewhere: no signal
    assert sorted(browser.selected_keys()) == [1, 3] and seen == []
    browser._table.selectRow(0)  # the user selects: signal with the keys
    assert seen and seen[-1] == [0]
    browser.set_selected_keys([2], emit=True)
    assert seen[-1] == [2]
