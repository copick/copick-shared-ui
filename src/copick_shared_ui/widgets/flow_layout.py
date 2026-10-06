"""A layout that wraps its items onto new lines, so a row of buttons never sets a wide minimum width on a narrow dock
(the Qt flow-layout example, with height-for-width)."""

from qtpy.QtCore import QPoint, QRect, QSize, Qt
from qtpy.QtWidgets import QLayout, QSizePolicy


class FlowLayout(QLayout):
    """Items left to right, wrapping onto new lines; each line's items are centred vertically (buttons, spin boxes
    and combo boxes of different heights line up), and with ``center=True`` each line is centred horizontally."""

    def __init__(self, parent=None, margin: int = 0, h_spacing: int = 4, v_spacing: int = 4, center: bool = False):
        super().__init__(parent)
        self._items = []
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing
        self._center = center
        self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item):  # noqa: N802 (Qt API)
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):  # noqa: N802
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):  # noqa: N802
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):  # noqa: N802
        return Qt.Orientation(0)

    def hasHeightForWidth(self):  # noqa: N802
        return True

    def heightForWidth(self, width):  # noqa: N802
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect):  # noqa: N802
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self):  # noqa: N802
        return self.minimumSize()

    def minimumSize(self):  # noqa: N802
        """The widest single item: the layout wraps everything else."""
        size = QSize()
        for item in self._items:
            widget = item.widget()
            size = size.expandedTo(widget.minimumSizeHint() if widget is not None else item.minimumSize())
        m = self.contentsMargins()
        return size + QSize(m.left() + m.right(), m.top() + m.bottom())

    def _do_layout(self, rect, test_only: bool) -> int:
        m = self.contentsMargins()
        effective = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        # Break the items into lines, then place each line (vertically centred, optionally horizontally centred).
        lines, line, width = [], [], 0
        for item in self._items:
            widget = item.widget()
            if widget is not None and widget.isHidden():
                continue
            # Widgets get their own size hint: through the layout item, macOS shaves the push button's visual margins
            # off its height, and a push button shorter than its native height is drawn as a square bevel button.
            hint = widget.sizeHint().expandedTo(widget.minimumSizeHint()) if widget is not None else item.sizeHint()
            needed = hint.width() if not line else width + self._h_spacing + hint.width()
            if line and needed > effective.width():
                lines.append((line, width))
                line, width = [], 0
                needed = hint.width()
            line.append((item, widget, hint))
            width = needed
        if line:
            lines.append((line, width))
        y = effective.y()
        for i, (line, width) in enumerate(lines):
            line_height = max(h.height() for _i, _w, h in line)
            x = effective.x() + (max(0, effective.width() - width) // 2 if self._center else 0)
            if not test_only:
                for item, widget, hint in line:
                    pos = QPoint(x, y + (line_height - hint.height()) // 2)
                    if widget is not None:
                        widget.setGeometry(QRect(pos, hint))
                    else:
                        item.setGeometry(QRect(pos, hint))
                    x += hint.width() + self._h_spacing
            y += line_height + (self._v_spacing if i < len(lines) - 1 else 0)
        return y - rect.y() + m.bottom()


def flow_container(*widgets, parent=None):
    """A widget holding ``widgets`` in a FlowLayout (preferred width, grows in height when narrow)."""
    from qtpy.QtWidgets import QWidget

    w = QWidget(parent)
    layout = FlowLayout(w)
    for child in widgets:
        layout.addWidget(child)
    policy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
    policy.setHeightForWidth(True)
    w.setSizePolicy(policy)
    return w
