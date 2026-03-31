"""URI builder widget for copick CLI tool forms.

Provides a text field + browse popup that lets users construct copick URIs
from project data, while still supporting raw URI editing and patterns.
"""

from typing import Any, Callable, List, Optional, Tuple

try:
    from qtpy.QtCore import QPoint, QRect, Qt
    from qtpy.QtWidgets import (
        QApplication,
        QComboBox,
        QDialog,
        QFormLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QPushButton,
        QSizePolicy,
        QToolButton,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    from Qt.QtCore import QPoint, QRect, Qt
    from Qt.QtWidgets import (
        QApplication,
        QComboBox,
        QDialog,
        QFormLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QPushButton,
        QSizePolicy,
        QToolButton,
        QVBoxLayout,
        QWidget,
    )

from copick_shared_ui.core.click_schema import URIParamMeta
from copick_shared_ui.core.models import AbstractCLIContextInterface

# URI format templates per object type
_URI_FIELDS = {
    "picks": ["object_name", "user_id", "session_id"],
    "mesh": ["object_name", "user_id", "session_id"],
    "segmentation": ["object_name", "user_id", "session_id", "voxel_spacing"],
    "tomogram": ["tomo_type", "voxel_spacing"],
    "feature": ["tomo_type", "voxel_spacing", "feature_type"],
    "any": ["object_name", "user_id", "session_id"],
}

_FIELD_LABELS = {
    "object_name": "Object Name",
    "user_id": "User ID",
    "session_id": "Session ID",
    "voxel_spacing": "Voxel Spacing",
    "tomo_type": "Tomogram Type",
    "feature_type": "Feature Type",
}


def _assemble_uri(object_type: str, values: dict) -> str:
    """Assemble a URI string from component values."""
    if object_type in ("picks", "mesh", "any"):
        obj = values.get("object_name", "")
        user = values.get("user_id", "")
        session = values.get("session_id", "")
        if not obj:
            return ""
        parts = obj
        if user or session:
            parts += f":{user}/{session}"
        return parts

    elif object_type == "segmentation":
        name = values.get("object_name", "")
        user = values.get("user_id", "")
        session = values.get("session_id", "")
        vs = values.get("voxel_spacing", "")
        if not name:
            return ""
        parts = name
        if user or session:
            parts += f":{user}/{session}"
        if vs:
            parts += f"@{vs}"
        return parts

    elif object_type == "tomogram":
        ttype = values.get("tomo_type", "")
        vs = values.get("voxel_spacing", "")
        if not ttype:
            return ""
        if vs:
            return f"{ttype}@{vs}"
        return ttype

    elif object_type == "feature":
        ttype = values.get("tomo_type", "")
        vs = values.get("voxel_spacing", "")
        ftype = values.get("feature_type", "")
        if not ttype:
            return ""
        parts = ttype
        if vs:
            parts += f"@{vs}"
        if ftype:
            parts += f":{ftype}"
        return parts

    return ""


def _parse_uri_simple(object_type: str, uri: str) -> dict:
    """Simple URI parser that extracts components. Does not validate."""
    result = {}
    if not uri:
        return result

    if object_type in ("picks", "mesh", "any"):
        # object_name:user_id/session_id
        if ":" in uri:
            obj, rest = uri.split(":", 1)
            result["object_name"] = obj
            if "/" in rest:
                user, session = rest.split("/", 1)
                result["user_id"] = user
                result["session_id"] = session
            else:
                result["user_id"] = rest
        else:
            result["object_name"] = uri

    elif object_type == "segmentation":
        # name:user_id/session_id@voxel_spacing
        vs_part = ""
        main = uri
        if "@" in uri:
            main, vs_part = uri.rsplit("@", 1)
            result["voxel_spacing"] = vs_part
        if ":" in main:
            name, rest = main.split(":", 1)
            result["object_name"] = name
            if "/" in rest:
                user, session = rest.split("/", 1)
                result["user_id"] = user
                result["session_id"] = session
            else:
                result["user_id"] = rest
        else:
            result["object_name"] = main

    elif object_type == "tomogram":
        # tomo_type@voxel_spacing
        if "@" in uri:
            ttype, vs = uri.split("@", 1)
            result["tomo_type"] = ttype
            result["voxel_spacing"] = vs
        else:
            result["tomo_type"] = uri

    elif object_type == "feature":
        # tomo_type@voxel_spacing:feature_type
        if "@" in uri:
            ttype, rest = uri.split("@", 1)
            result["tomo_type"] = ttype
            if ":" in rest:
                vs, ftype = rest.split(":", 1)
                result["voxel_spacing"] = vs
                result["feature_type"] = ftype
            else:
                result["voxel_spacing"] = rest
        else:
            result["tomo_type"] = uri

    return result


def _get_field_items(
    field_name: str,
    context: AbstractCLIContextInterface,
) -> List[str]:
    """Get available items for a URI field from project context."""
    if field_name == "object_name":
        return context.get_object_names()
    elif field_name == "user_id":
        return context.get_user_ids()
    elif field_name == "session_id":
        return context.get_session_ids()
    elif field_name == "voxel_spacing":
        return [str(v) for v in context.get_voxel_spacings()]
    elif field_name == "tomo_type":
        return context.get_tomo_types()
    return []


class _URIBrowsePopup(QDialog):
    """Dialog with cascading comboboxes for building a copick URI."""

    def __init__(
        self,
        uri_meta: URIParamMeta,
        context: AbstractCLIContextInterface,
        current_uri: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Build {uri_meta.object_type} URI")
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.uri_meta = uri_meta
        self.context = context
        self._combos: dict = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Header
        header = QLabel(f"<b>Build {uri_meta.object_type} URI</b>")
        layout.addWidget(header)

        # Form with comboboxes
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        fields = _URI_FIELDS.get(uri_meta.object_type, _URI_FIELDS["any"])
        parsed = _parse_uri_simple(uri_meta.object_type, current_uri)

        for field_name in fields:
            combo = QComboBox()
            combo.setEditable(True)
            combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(12)
            combo.setMinimumWidth(180)

            # Populate from context
            items = _get_field_items(field_name, context)
            combo.addItem("")  # empty option
            combo.addItems(items)

            # Add output-specific template suggestions
            if uri_meta.role == "output" and field_name == "session_id":
                for tmpl in ["{input_session_id}", "{instance_id}"]:
                    if combo.findText(tmpl) < 0:
                        combo.addItem(tmpl)

            # Pre-fill from current URI
            if field_name in parsed:
                val = parsed[field_name]
                idx = combo.findText(val)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                else:
                    combo.setCurrentText(val)

            label = _FIELD_LABELS.get(field_name, field_name)
            form.addRow(label, combo)
            self._combos[field_name] = combo

        layout.addLayout(form)

        # Apply button
        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self._on_apply)
        layout.addWidget(apply_btn)

        self._result_uri: Optional[str] = None

    def _on_apply(self) -> None:
        values = {}
        for field_name, combo in self._combos.items():
            values[field_name] = combo.currentText().strip()
        self._result_uri = _assemble_uri(self.uri_meta.object_type, values)
        self.accept()

    def get_result(self) -> Optional[str]:
        return self._result_uri


class CopickURIWidget(QWidget):
    """URI input widget with a text field and structured browse popup.

    The text field supports raw URI editing (including patterns/regex).
    The browse button opens a popup with comboboxes populated from project data.
    """

    def __init__(
        self,
        uri_meta: URIParamMeta,
        context: AbstractCLIContextInterface,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.uri_meta = uri_meta
        self.context = context

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.line_edit = QLineEdit()
        layout.addWidget(self.line_edit)

        self.browse_btn = QToolButton()
        self.browse_btn.setText("\U0001f4c2")  # 📂
        self.browse_btn.setFixedWidth(28)
        self.browse_btn.setCursor(Qt.PointingHandCursor)
        self.browse_btn.setToolTip("Browse project data to build URI")
        self.browse_btn.clicked.connect(self._open_popup)
        layout.addWidget(self.browse_btn)

    def _open_popup(self) -> None:
        popup = _URIBrowsePopup(
            uri_meta=self.uri_meta,
            context=self.context,
            current_uri=self.line_edit.text().strip(),
            parent=self,
        )
        # Ensure the popup knows its size before positioning
        popup.adjustSize()
        popup_size = popup.sizeHint()

        # Position below the button, then clamp to screen
        pos = self.browse_btn.mapToGlobal(QPoint(0, self.browse_btn.height() + 2))

        # Get the screen geometry for the screen the button is on
        screen = QApplication.screenAt(self.browse_btn.mapToGlobal(QPoint(0, 0)))
        if screen is not None:
            screen_rect = screen.availableGeometry()
        else:
            screen_rect = QRect(0, 0, 1920, 1080)

        # Clamp horizontal: if popup overflows right edge, shift left
        if pos.x() + popup_size.width() > screen_rect.right():
            pos.setX(screen_rect.right() - popup_size.width())
        if pos.x() < screen_rect.left():
            pos.setX(screen_rect.left())

        # Clamp vertical: if popup overflows bottom, show above the button instead
        if pos.y() + popup_size.height() > screen_rect.bottom():
            pos = self.browse_btn.mapToGlobal(QPoint(0, -popup_size.height() - 2))
        if pos.y() < screen_rect.top():
            pos.setY(screen_rect.top())

        popup.move(pos)
        if popup.exec_() == QDialog.Accepted:
            result = popup.get_result()
            if result is not None:
                self.line_edit.setText(result)

    def get_value(self) -> Any:
        text = self.line_edit.text().strip()
        return text if text else None

    def set_value(self, val: Any) -> None:
        try:
            if val is not None:
                self.line_edit.setText(str(val))
            else:
                self.line_edit.clear()
        except RuntimeError:
            pass  # Widget already deleted by Qt
