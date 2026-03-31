"""Dynamic actions bar showing applicable tools for the selected tree item.

Displays tool buttons below the tree view that match the selected copick
object type. Clicking a button emits a signal to navigate to the tool form.
"""

from typing import Any, List, Optional

try:
    from qtpy.QtCore import Qt, Signal
    from qtpy.QtWidgets import (
        QHBoxLayout,
        QLabel,
        QPushButton,
        QScrollArea,
        QSizePolicy,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    from Qt.QtCore import Qt, Signal
    from Qt.QtWidgets import (
        QHBoxLayout,
        QLabel,
        QPushButton,
        QScrollArea,
        QSizePolicy,
        QVBoxLayout,
        QWidget,
    )

from copick_shared_ui.core.click_schema import CommandSchema, get_applicable_commands


class _FlowLayout(QVBoxLayout):
    """Simple flow-like layout using wrapped QHBoxLayouts.

    Not a true flow layout, but wraps buttons into rows that fit the width.
    We use a simple approach: put all buttons in a horizontal scroll area.
    """

    pass


class ActionsBar(QWidget):
    """Dynamic bar showing applicable tool buttons for the selected copick object.

    Emits `tool_requested` with the CommandSchema and pre-fill URI string
    when a tool button is clicked.
    """

    tool_requested = Signal(object, str)  # (CommandSchema, uri_string)

    def __init__(
        self,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._schemas: List[CommandSchema] = []
        self._current_uri: str = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        # Header showing what's selected
        self._header = QLabel()
        self._header.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self._header)

        # Scrollable button area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setMaximumHeight(36)

        self._btn_container = QWidget()
        self._btn_layout = QHBoxLayout(self._btn_container)
        self._btn_layout.setContentsMargins(0, 0, 0, 0)
        self._btn_layout.setSpacing(4)
        self._btn_layout.addStretch()

        scroll.setWidget(self._btn_container)
        layout.addWidget(scroll)

        # Initially hidden
        self.setVisible(False)

    def set_available_commands(self, schemas: List[CommandSchema]) -> None:
        """Set the full list of discovered command schemas for matching."""
        self._schemas = schemas

    def update_for_object(self, copick_obj: Any) -> None:
        """Update the actions bar for the given copick object.

        Shows applicable tool buttons if the object type matches any commands.
        Hides the bar if no tools are applicable.
        """
        # Determine object type
        obj_type = self._get_object_type(copick_obj)
        if obj_type is None:
            self.setVisible(False)
            return

        # Serialize URI
        try:
            from copick.util.uri import serialize_copick_uri

            self._current_uri = serialize_copick_uri(copick_obj)
        except Exception:
            self._current_uri = ""

        # Find applicable commands
        applicable = get_applicable_commands(self._schemas, obj_type)
        if not applicable:
            self.setVisible(False)
            return

        # Update header
        display_type = obj_type.replace("_", " ").title()
        uri_display = self._current_uri if self._current_uri else "selected item"
        self._header.setText(f"\U0001f527 {display_type}: {uri_display}")

        # Clear existing buttons
        while self._btn_layout.count() > 1:  # Keep the stretch
            item = self._btn_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add tool buttons
        for schema in applicable:
            btn = QPushButton(schema.name)
            btn.setToolTip(schema.short_help)
            btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            btn.setCursor(Qt.PointingHandCursor)

            # Capture schema in closure
            def _make_handler(s):
                return lambda: self.tool_requested.emit(s, self._current_uri)

            btn.clicked.connect(_make_handler(schema))
            self._btn_layout.insertWidget(self._btn_layout.count() - 1, btn)

        self.setVisible(True)

    @staticmethod
    def _get_object_type(copick_obj: Any) -> Optional[str]:
        """Map a copick model object to its URI object type string."""
        if copick_obj is None:
            return None
        cls_name = type(copick_obj).__name__
        if "Picks" in cls_name:
            return "picks"
        elif "Mesh" in cls_name:
            return "mesh"
        elif "Segmentation" in cls_name:
            return "segmentation"
        elif "Tomogram" in cls_name:
            return "tomogram"
        elif "Features" in cls_name:
            return "feature"
        return None
