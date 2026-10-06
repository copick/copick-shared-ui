"""Compact two-line rows for item views (napari and ChimeraX).

Line 1: optional icon, colour swatch, title (the display text) and a small type chip; line 2: a dimmer caption.
Models keep their data; the delegate only paints it, so filtering, selection, double-click and background tints
work as before. Roles:

- ``Qt.DisplayRole``: the title;
- ``CAPTION_ROLE``: the second line;
- ``CHIP_ROLE`` / ``CHIP_COLOR_ROLE``: chip text and an optional ``QColor``;
- ``SWATCH_ROLE``: a ``QColor`` (or anything ``QColor`` accepts), or ``"multi"`` for a multi-colour swatch;
- ``Qt.DecorationRole``: an optional icon at the left, centred over both lines.

``make_compact(view)`` installs the delegate on a table view (one stretching column, uniform row height) and
``install_sort_menu`` turns its header into a "sort by" menu, since one column can no longer sort by clicking.
"""

import contextlib
from typing import Callable, Optional, Sequence, Tuple

from qtpy.QtCore import QEvent, QObject, QPoint, QPointF, QRect, QRectF, QSize, Qt
from qtpy.QtGui import QBrush, QColor, QConicalGradient, QFont, QFontMetrics, QIcon, QPainter, QPalette, QPen
from qtpy.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHeaderView,
    QMenu,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
)

CAPTION_ROLE = Qt.UserRole + 101
CHIP_ROLE = Qt.UserRole + 102
CHIP_COLOR_ROLE = Qt.UserRole + 103
SWATCH_ROLE = Qt.UserRole + 104

MULTI_SWATCH = "multi"

_PAD_X = 6
_PAD_Y = 3
_GAP = 5
_SWATCH = 10
_ICON = 16
_MIN_TITLE = 40
_CAPTION_SCALE = 0.85
_CHIP_SCALE = 0.75


def _outline_color(palette: QPalette) -> QColor:
    """The selected-row outline: the application's highlight colour (the view's own is cleared), lightened when the
    background is dark so it stands out against tinted rows."""
    color = QColor(QApplication.palette().color(QPalette.Active, QPalette.Highlight))
    if color.alpha() == 0:
        color = QColor(42, 130, 218)
    if palette.color(QPalette.Base).lightness() < 128 and color.lightness() < 150:
        color = color.lighter(170)
    color.setAlpha(255)
    return color


def _scaled(font: QFont, factor: float, bold: Optional[bool] = None) -> QFont:
    f = QFont(font)
    if f.pointSizeF() > 0:
        f.setPointSizeF(max(6.0, f.pointSizeF() * factor))
    elif f.pixelSize() > 0:
        f.setPixelSize(max(8, round(f.pixelSize() * factor)))
    if bold is not None:
        f.setBold(bold)
    return f


class CompactItemDelegate(QStyledItemDelegate):
    """Paints an item as two lines, ``[icon] [swatch] title [chip] / caption``, or with ``inline=True`` as one line,
    ``[icon] [swatch] title [chip] caption`` (dense lists whose captions are short, like instance browsers).

    Selected rows keep their background (the row tint carries the object's or instance's colour) and get an outline
    in the palette's highlight colour instead of a fill. Installed for a whole view (``make_compact``), the delegate
    draws other columns the standard way (check boxes, text) with the same outline, so it spans the row.
    """

    def __init__(self, parent: Optional[QObject] = None, min_width: int = 60, inline: bool = False):
        super().__init__(parent)
        self._min_width = min_width
        self.inline = inline
        self.compact_column = 0
        #: Colour of the selected row's outline; default: the application's highlight colour, lightened on dark themes.
        self.outline_color: Optional[QColor] = None

    # -- geometry ------------------------------------------------------------------------------------------------

    def row_height(self, font: QFont) -> int:
        """Height of a two-line row for ``font`` (use for uniform row heights)."""
        title = QFontMetrics(font).height()
        if self.inline:
            return title + 2 * _PAD_Y + 2
        caption = QFontMetrics(_scaled(font, _CAPTION_SCALE)).height()
        return title + caption + 2 * _PAD_Y + 1

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:  # noqa: N802 (Qt API)
        height = self.row_height(option.font)
        if index.column() != self.compact_column:  # check boxes, plain text: their natural width
            return QSize(super().sizeHint(option, index).width(), height)
        return QSize(self._min_width, height)

    # -- painting ------------------------------------------------------------------------------------------------

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        selected = bool(option.state & QStyle.State_Selected)
        if index.column() != self.compact_column:  # check boxes and plain text, outlined like the compact cell
            opt = QStyleOptionViewItem(option)
            opt.state &= ~(QStyle.State_Selected | QStyle.State_HasFocus)
            super().paint(painter, opt, index)
            if selected:
                self._paint_outline(painter, option, index)
            return

        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        title = opt.text or ""
        icon = QIcon(opt.icon) if not opt.icon.isNull() else None  # a copy: opt.icon is cleared below
        # Native background (hover, stylesheets, BackgroundRole tints) without the selection fill.
        opt.text = ""
        opt.icon = QIcon()
        opt.state &= ~(QStyle.State_Selected | QStyle.State_HasFocus)
        widget = opt.widget
        style = widget.style() if widget is not None else QApplication.style()
        style.drawControl(QStyle.CE_ItemViewItem, opt, painter, widget)

        text_color = opt.palette.color(QPalette.Text)
        caption_color = QColor(text_color)
        caption_color.setAlpha(165)

        caption = index.data(CAPTION_ROLE) or ""
        chip = index.data(CHIP_ROLE) or ""
        swatch = index.data(SWATCH_ROLE)

        title_font = QFont(opt.font)
        caption_font = _scaled(opt.font, _CAPTION_SCALE)
        title_fm, caption_fm = QFontMetrics(title_font), QFontMetrics(caption_font)

        rect = opt.rect.adjusted(_PAD_X, _PAD_Y, -_PAD_X, -_PAD_Y)
        top = rect.top() + (rect.height() - title_fm.height()) // 2 if self.inline else rect.top()
        line1 = QRect(rect.left(), top, rect.width(), title_fm.height())
        line2 = QRect(rect.left(), line1.bottom() + 1, rect.width(), caption_fm.height())

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        x = rect.left()
        if icon is not None:
            size = min(_ICON, rect.height())
            icon_rect = QRect(x, rect.top() + (rect.height() - size) // 2, size, size)
            mode = QIcon.Selected if selected else QIcon.Normal
            icon.paint(painter, icon_rect, Qt.AlignCenter, mode)
            x += size + _GAP
        text_left = x  # the caption lines up with the title's swatch

        if swatch is not None and swatch != "":
            sw = QRectF(x, line1.center().y() - _SWATCH / 2 + 0.5, _SWATCH, _SWATCH)
            self._paint_swatch(painter, sw, swatch, text_color)
            x += _SWATCH + _GAP

        # Title and chip share line 1: the title elides first, the chip goes when the title would get too short.
        chip_font = _scaled(opt.font, _CHIP_SCALE)
        chip_fm = QFontMetrics(chip_font)
        chip_w = chip_fm.horizontalAdvance(chip) + 8 if chip else 0
        avail = line1.right() - x + 1
        show_chip = bool(chip) and avail - chip_w - _GAP >= _MIN_TITLE
        title_avail = avail - (chip_w + _GAP if show_chip else 0)
        shown = title_fm.elidedText(title, Qt.ElideRight, max(0, title_avail))
        painter.setFont(title_font)
        painter.setPen(text_color)
        painter.drawText(
            QRect(x, line1.top(), max(0, title_avail), line1.height()),
            Qt.AlignLeft | Qt.AlignVCenter,
            shown,
        )
        end = x + title_fm.horizontalAdvance(shown)
        if show_chip:
            cx = end + _GAP
            chip_rect = QRectF(cx, line1.center().y() - chip_fm.height() / 2, chip_w, chip_fm.height())
            self._paint_chip(painter, chip_rect, chip, chip_font, index.data(CHIP_COLOR_ROLE), text_color)
            end = cx + chip_w

        if caption and self.inline:  # the rest of line 1
            cap_rect = QRect(end + 2 * _GAP, line1.top(), line1.right() - end - 2 * _GAP + 1, line1.height())
            if cap_rect.width() > 20:
                painter.setFont(caption_font)
                painter.setPen(caption_color)
                painter.drawText(
                    cap_rect,
                    Qt.AlignLeft | Qt.AlignVCenter,
                    caption_fm.elidedText(caption, Qt.ElideRight, cap_rect.width()),
                )
        elif caption:
            painter.setFont(caption_font)
            painter.setPen(caption_color)
            cap_rect = QRect(text_left, line2.top(), line2.right() - text_left + 1, line2.height())
            painter.drawText(
                cap_rect,
                Qt.AlignLeft | Qt.AlignVCenter,
                caption_fm.elidedText(caption, Qt.ElideRight, cap_rect.width()),
            )
        painter.restore()
        if selected:
            self._paint_outline(painter, option, index)

    def _paint_outline(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        """The selected row's outline: top and bottom edges on every cell, left on the first column, right on the
        last, so adjacent cells join into one frame around the row."""
        model = index.model()
        first = index.column() == 0
        last = model is None or index.column() == model.columnCount(index.parent()) - 1
        color = self.outline_color or _outline_color(option.palette)
        width = 2
        r = QRectF(option.rect).adjusted(width / 2, width / 2, -width / 2, -width / 2)
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.setPen(QPen(color, width))
        left = r.left() if first else option.rect.left()
        right = r.right() if last else option.rect.right() + 1
        painter.drawLine(QPointF(left, r.top()), QPointF(right, r.top()))
        painter.drawLine(QPointF(left, r.bottom()), QPointF(right, r.bottom()))
        if first:
            painter.drawLine(QPointF(r.left(), r.top()), QPointF(r.left(), r.bottom()))
        if last:
            painter.drawLine(QPointF(r.right(), r.top()), QPointF(r.right(), r.bottom()))
        painter.restore()

    @staticmethod
    def _paint_swatch(painter: QPainter, rect: QRectF, swatch, outline: QColor) -> None:
        if swatch == MULTI_SWATCH:
            gradient = QConicalGradient(rect.center(), 90)
            for stop, hue in ((0.0, 0), (0.17, 40), (0.33, 60), (0.5, 120), (0.67, 210), (0.83, 280), (1.0, 360)):
                gradient.setColorAt(stop, QColor.fromHsv(hue % 360, 200, 240))
            brush = QBrush(gradient)
        else:
            color = QColor(swatch) if not isinstance(swatch, QColor) else swatch
            if not color.isValid():
                return
            brush = QBrush(color)
        edge = QColor(outline)
        edge.setAlpha(90)
        painter.setPen(QPen(edge, 1))
        painter.setBrush(brush)
        painter.drawEllipse(rect)

    @staticmethod
    def _paint_chip(painter: QPainter, rect: QRectF, text: str, font: QFont, color, fallback: QColor) -> None:
        c = QColor(color) if color is not None else QColor(fallback)
        if not c.isValid():
            c = QColor(fallback)
        edge = QColor(c)
        edge.setAlpha(200)
        painter.setPen(QPen(edge, 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        painter.setFont(font)
        painter.setPen(c)
        painter.drawText(rect, Qt.AlignCenter, text)


class _CompactKeeper(QObject):
    """Keeps a compact view compact: re-applies the column resize modes when the view gets a model (Qt resets
    per-section modes when the section count changes) and the uniform row height when its font or style changes."""

    def __init__(self, view: QTableView, delegate: CompactItemDelegate, column: int):
        super().__init__(view)
        self._view, self._delegate, self._column = view, delegate, column
        view.horizontalHeader().sectionCountChanged.connect(lambda *_: self.apply_columns())
        self.clear_selection_fill()
        self.apply()

    def clear_selection_fill(self) -> None:
        """No selection fill, so a selected row keeps its colour (the delegate outlines it instead).

        Native styles fill a selected row with the palette's highlight colour before the delegate paints (the row
        background), so the view's own highlight becomes transparent and the delegate keeps the real one for the
        outline. Under an inherited style sheet (napari) a ``::item:selected`` rule fills it instead, so the view gets
        a transparent rule of its own, which wins over inherited ones.
        """
        view = self._view
        pal = view.palette()
        for group in (QPalette.Active, QPalette.Inactive):
            pal.setColor(group, QPalette.Highlight, QColor(0, 0, 0, 0))
        view.setPalette(pal)

    def _inherits_style_sheet(self) -> bool:
        w = self._view.parentWidget()
        while w is not None:
            if w.styleSheet():
                return True
            w = w.parentWidget()
        app = QApplication.instance()
        return bool(app is not None and app.styleSheet())

    def ensure_style_sheet_rule(self) -> None:
        rule = "QTableView::item:selected { background: transparent; }"
        if rule not in self._view.styleSheet() and self._inherits_style_sheet():
            self._view.setStyleSheet(f"{self._view.styleSheet()}\n{rule}".strip())

    def apply(self) -> None:
        self.apply_columns()
        h = self._delegate.row_height(self._view.font())
        vh = self._view.verticalHeader()
        vh.setMinimumSectionSize(h)
        vh.setDefaultSectionSize(h)

    def apply_columns(self) -> None:
        header = self._view.horizontalHeader()
        for section in range(header.count()):
            mode = QHeaderView.Stretch if section == self._column else QHeaderView.ResizeToContents
            header.setSectionResizeMode(section, mode)

    def _wrap(self, key) -> bool:
        """Up on the first row goes to the last, Down on the last to the first (rows hidden by a filter skipped).
        Returns True if the key was handled; at the ends Qt would otherwise ignore it and pass it on."""
        view = self._view
        model = view.model()
        if model is None or model.rowCount() == 0:
            return False
        shown = [r for r in range(model.rowCount()) if not view.isRowHidden(r)]
        if not shown:
            return False
        current = view.currentIndex()
        row = current.row() if current.isValid() else -1
        if key == Qt.Key_Up and (row < 0 or row <= shown[0]):
            target = shown[-1]
        elif key == Qt.Key_Down and (row < 0 or row >= shown[-1]):
            target = shown[0]
        else:
            return False
        column = current.column() if current.isValid() else self._column
        index = model.index(target, column)
        view.setCurrentIndex(index)
        view.scrollTo(index)
        return True

    def eventFilter(self, obj, event):  # noqa: N802 (Qt API)
        if event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Up, Qt.Key_Down) and not event.modifiers():
            return self._wrap(event.key())
        if event.type() in (QEvent.FontChange, QEvent.StyleChange):
            self.apply()
        elif event.type() in (QEvent.Show, QEvent.ParentChange):
            self.ensure_style_sheet_rule()
        return False


def make_compact(
    view: QTableView,
    delegate: Optional[CompactItemDelegate] = None,
    column: int = 0,
) -> CompactItemDelegate:
    """Draw ``column`` of a table view with a ``CompactItemDelegate``: it stretches, other columns fit their
    contents, rows have a uniform two-line height, selected rows are outlined and the vertical header is hidden."""
    delegate = delegate or CompactItemDelegate(view)
    delegate.compact_column = column
    view.setItemDelegate(delegate)
    view.setWordWrap(False)
    view.setShowGrid(False)
    view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    view.setTextElideMode(Qt.ElideRight)
    view.verticalHeader().setVisible(False)
    header = view.horizontalHeader()
    header.setMinimumSectionSize(16)
    header.setSectionResizeMode(QHeaderView.ResizeToContents)
    header.setStretchLastSection(True)
    header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    view.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
    keeper = _CompactKeeper(view, delegate, column)
    view.installEventFilter(keeper)
    view._compact_keeper = keeper  # keep a reference with the view
    return delegate


class SortMenu(QObject):
    """A "sort by" menu on a header: clicking the header shows the keys (plus Descending); the chosen key is shown
    in the header text, e.g. ``Name ▾ · by user``."""

    def __init__(
        self,
        header: QHeaderView,
        label: str,
        options: Sequence[Tuple[str, str]],
        on_select: Callable[[str, bool], None],
        current: Optional[str] = None,
        descending: bool = False,
        column: int = 0,
    ):
        super().__init__(header)
        self._header = header
        self._label = label
        self._options = list(options)
        self._on_select = on_select
        self._column = column
        self.key = current or (self._options[0][0] if self._options else "")
        self.descending = descending
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(False)
        header.setToolTip("Click to choose the sort order")
        # A clickable header would also select the whole column (all rows) when pressed; the click is a menu here.
        with contextlib.suppress(TypeError, RuntimeError):
            header.sectionPressed.disconnect()
        header.sectionClicked.connect(self._on_section_clicked)
        self._update_label()

    def refresh(self) -> None:
        """Re-apply the header text (after the view got a new model)."""
        self._update_label()

    def set_options(self, options: Sequence[Tuple[str, str]]) -> None:
        self._options = list(options)
        if self._options and self.key not in {k for k, _ in self._options}:
            self.key = self._options[0][0]
        self._update_label()

    def set_label(self, label: str) -> None:
        self._label = label
        self._update_label()

    def select(self, key: str, descending: Optional[bool] = None) -> None:
        self.key = key
        if descending is not None:
            self.descending = descending
        self._update_label()
        self._on_select(self.key, self.descending)

    def menu(self) -> QMenu:
        menu = QMenu(self._header)
        for key, text in self._options:
            action = menu.addAction(text)
            action.setCheckable(True)
            action.setChecked(key == self.key)
            action.triggered.connect(lambda _checked=False, k=key: self.select(k))
        menu.addSeparator()
        desc = menu.addAction("Descending")
        desc.setCheckable(True)
        desc.setChecked(self.descending)
        desc.triggered.connect(lambda checked: self.select(self.key, bool(checked)))
        return menu

    def _on_section_clicked(self, section: int) -> None:
        if section != self._column:
            return
        x = self._header.sectionViewportPosition(section)
        self.menu().exec_(self._header.mapToGlobal(QPoint(x, self._header.height())))

    def _update_label(self) -> None:
        names = dict(self._options)
        arrow = " ▾"
        text = self._label + arrow
        if self.key and names.get(self.key) and self.key != (self._options[0][0] if self._options else None):
            text += f" · by {names[self.key].lower()}"
        if self.descending:
            text += " ↓"
        model = self._header.model()
        done = model is not None and model.setHeaderData(self._column, Qt.Horizontal, text, Qt.DisplayRole)
        view = self._header.parent()
        if not done and isinstance(view, QTableWidget):  # a QTableWidget needs a header item to hold the text
            item = view.horizontalHeaderItem(self._column) or QTableWidgetItem()
            item.setText(text)
            view.setHorizontalHeaderItem(self._column, item)
        self._header.viewport().update()
        self.text = text
