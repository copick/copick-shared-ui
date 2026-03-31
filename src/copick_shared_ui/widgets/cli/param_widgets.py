"""Factory functions mapping Click parameter types to Qt widgets.

Each factory returns a tuple of (widget, get_value, set_value) so that the
command form can read and write parameter values generically.
"""

from typing import Any, Callable, List, Optional, Tuple

try:
    from qtpy.QtCore import Qt
    from qtpy.QtWidgets import (
        QCheckBox,
        QComboBox,
        QDoubleSpinBox,
        QFileDialog,
        QHBoxLayout,
        QLineEdit,
        QPushButton,
        QSizePolicy,
        QSpinBox,
        QWidget,
    )
except ImportError:
    from Qt.QtCore import Qt
    from Qt.QtWidgets import (
        QCheckBox,
        QComboBox,
        QDoubleSpinBox,
        QFileDialog,
        QHBoxLayout,
        QLineEdit,
        QPushButton,
        QSizePolicy,
        QSpinBox,
        QWidget,
    )

from copick_shared_ui.core.click_schema import ParamSchema
from copick_shared_ui.core.models import AbstractCLIContextInterface

# Type alias for the widget factory return type
ParamWidgetResult = Tuple[QWidget, Callable[[], Any], Callable[[Any], None]]


def _create_string_widget(
    param: ParamSchema,
    context: Optional[AbstractCLIContextInterface] = None,
    parent: Optional[QWidget] = None,
) -> ParamWidgetResult:
    """Create a QLineEdit for string parameters."""
    widget = QLineEdit(parent)
    if param.default is not None and param.default != "":
        widget.setText(str(param.default))

    def get_value() -> Any:
        text = widget.text().strip()
        if param.multiple and text:
            return [v.strip() for v in text.split(",") if v.strip()]
        return text if text else None

    def set_value(val: Any) -> None:
        if isinstance(val, (list, tuple)):
            widget.setText(", ".join(str(v) for v in val))
        elif val is not None:
            widget.setText(str(val))
        else:
            widget.clear()

    return widget, get_value, set_value


def _create_combobox_widget(
    param: ParamSchema,
    items: List[str],
    editable: bool = True,
    parent: Optional[QWidget] = None,
) -> ParamWidgetResult:
    """Create a QComboBox for parameters with known value sets."""
    widget = QComboBox(parent)
    widget.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
    widget.setMinimumContentsLength(12)
    sp = widget.sizePolicy()
    sp.setHorizontalPolicy(QSizePolicy.Expanding)
    widget.setSizePolicy(sp)
    widget.setEditable(editable)
    if editable:
        widget.setInsertPolicy(QComboBox.NoInsert)

    # Add empty item for optional params
    if not param.required:
        widget.addItem("")
    widget.addItems(items)

    # Set default
    if param.default is not None and str(param.default):
        idx = widget.findText(str(param.default))
        if idx >= 0:
            widget.setCurrentIndex(idx)
        elif editable:
            widget.setCurrentText(str(param.default))

    def get_value() -> Any:
        text = widget.currentText().strip()
        return text if text else None

    def set_value(val: Any) -> None:
        if val is not None:
            idx = widget.findText(str(val))
            if idx >= 0:
                widget.setCurrentIndex(idx)
            elif editable:
                widget.setCurrentText(str(val))
        else:
            widget.setCurrentIndex(0)

    return widget, get_value, set_value


def _create_choice_widget(
    param: ParamSchema,
    parent: Optional[QWidget] = None,
) -> ParamWidgetResult:
    """Create a QComboBox for Click Choice parameters."""
    items = list(param.choices) if param.choices else []
    return _create_combobox_widget(param, items, editable=False, parent=parent)


def _create_int_widget(
    param: ParamSchema,
    parent: Optional[QWidget] = None,
) -> ParamWidgetResult:
    """Create a QSpinBox for integer parameters."""
    widget = QSpinBox(parent)
    # Default to non-negative; allow negative only if the default is negative
    min_val = 0
    if param.default is not None:
        try:
            if int(param.default) < 0:
                min_val = -999999
        except (ValueError, TypeError):
            pass
    widget.setRange(min_val, 999999)
    if param.default is not None:
        try:
            widget.setValue(int(param.default))
        except (ValueError, TypeError):
            pass

    def get_value() -> Any:
        return widget.value()

    def set_value(val: Any) -> None:
        if val is not None:
            try:
                widget.setValue(int(val))
            except (ValueError, TypeError):
                pass

    return widget, get_value, set_value


def _create_float_widget(
    param: ParamSchema,
    parent: Optional[QWidget] = None,
) -> ParamWidgetResult:
    """Create a QDoubleSpinBox for float parameters."""
    widget = QDoubleSpinBox(parent)
    # Default to non-negative; allow negative only if the default is negative
    min_val = 0.0
    if param.default is not None:
        try:
            if float(param.default) < 0:
                min_val = -999999.0
        except (ValueError, TypeError):
            pass
    widget.setRange(min_val, 999999.0)
    widget.setDecimals(4)
    widget.setSingleStep(0.1)
    if param.default is not None:
        try:
            widget.setValue(float(param.default))
        except (ValueError, TypeError):
            pass

    def get_value() -> Any:
        return widget.value()

    def set_value(val: Any) -> None:
        if val is not None:
            try:
                widget.setValue(float(val))
            except (ValueError, TypeError):
                pass

    return widget, get_value, set_value


def _create_bool_widget(
    param: ParamSchema,
    parent: Optional[QWidget] = None,
) -> ParamWidgetResult:
    """Create a QCheckBox for boolean flag parameters."""
    widget = QCheckBox(parent)
    if param.default is not None:
        widget.setChecked(bool(param.default))

    def get_value() -> Any:
        return widget.isChecked()

    def set_value(val: Any) -> None:
        widget.setChecked(bool(val) if val is not None else False)

    return widget, get_value, set_value


def _create_path_widget(
    param: ParamSchema,
    parent: Optional[QWidget] = None,
) -> ParamWidgetResult:
    """Create a QLineEdit + browse button for path parameters."""
    container = QWidget(parent)
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)

    line_edit = QLineEdit()
    if param.default is not None and param.default != "":
        line_edit.setText(str(param.default))

    browse_btn = QPushButton("Browse...")
    browse_btn.setFixedWidth(80)

    layout.addWidget(line_edit)
    layout.addWidget(browse_btn)

    def _browse() -> None:
        path, _ = QFileDialog.getOpenFileName(container, f"Select {param.human_name}")
        if path:
            line_edit.setText(path)

    browse_btn.clicked.connect(_browse)

    def get_value() -> Any:
        text = line_edit.text().strip()
        return text if text else None

    def set_value(val: Any) -> None:
        if val is not None:
            line_edit.setText(str(val))
        else:
            line_edit.clear()

    return container, get_value, set_value


def _create_uri_widget(
    param: ParamSchema,
    context: AbstractCLIContextInterface,
    parent: Optional[QWidget] = None,
) -> ParamWidgetResult:
    """Create a CopickURIWidget for URI parameters."""
    from copick_shared_ui.widgets.cli.uri_widget import CopickURIWidget

    widget = CopickURIWidget(
        uri_meta=param.uri_meta,
        context=context,
        parent=parent,
    )
    return widget, widget.get_value, widget.set_value


def create_param_widget(
    param: ParamSchema,
    context: Optional[AbstractCLIContextInterface] = None,
    parent: Optional[QWidget] = None,
) -> ParamWidgetResult:
    """Create the appropriate Qt widget for a Click parameter.

    Returns:
        Tuple of (widget, get_value_callable, set_value_callable).
    """
    # URI widgets (must check before other auto-fill types)
    if param.uri_meta is not None and context is not None:
        return _create_uri_widget(param, context, parent=parent)

    # Context-aware auto-fill widgets
    if context is not None and param.auto_fill_type:
        af = param.auto_fill_type
        if af == "run_names":
            items = context.get_run_names()
            if items:
                return _create_combobox_widget(param, items, editable=True, parent=parent)
        elif af == "user_id":
            items = context.get_user_ids()
            if items:
                return _create_combobox_widget(param, items, editable=True, parent=parent)
        elif af == "session_id":
            items = context.get_session_ids()
            if items:
                return _create_combobox_widget(param, items, editable=True, parent=parent)
        elif af == "voxel_spacing":
            spacings = context.get_voxel_spacings()
            if spacings:
                items = [str(v) for v in spacings]
                return _create_combobox_widget(param, items, editable=True, parent=parent)

    # Type-based widget selection
    if param.param_type == "choice" and param.choices:
        return _create_choice_widget(param, parent=parent)
    elif param.param_type == "bool" or param.is_flag:
        return _create_bool_widget(param, parent=parent)
    elif param.param_type == "int":
        return _create_int_widget(param, parent=parent)
    elif param.param_type == "float":
        return _create_float_widget(param, parent=parent)
    elif param.param_type == "path":
        return _create_path_widget(param, parent=parent)
    else:
        # Default to string widget
        return _create_string_widget(param, context=context, parent=parent)
