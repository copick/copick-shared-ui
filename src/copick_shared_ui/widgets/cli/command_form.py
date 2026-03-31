"""Auto-generated form widget for a single Click command.

Builds a Qt form from a CommandSchema, with grouped parameters, validation,
background execution, and output display.
"""

from typing import Any, Callable, Dict, Optional, Tuple

try:
    from qtpy.QtCore import QPoint, Qt, Signal
    from qtpy.QtWidgets import (
        QApplication,
        QFormLayout,
        QFrame,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QProgressBar,
        QPushButton,
        QScrollArea,
        QTextEdit,
        QToolButton,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    from Qt.QtCore import QPoint, Qt, Signal
    from Qt.QtWidgets import (
        QApplication,
        QFormLayout,
        QFrame,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QProgressBar,
        QPushButton,
        QScrollArea,
        QTextEdit,
        QToolButton,
        QVBoxLayout,
        QWidget,
    )

from copick_shared_ui.core.click_schema import CommandSchema, ParamSchema, _HIDDEN_PARAMS
from copick_shared_ui.core.models import (
    AbstractCLIContextInterface,
    AbstractCLIRefreshInterface,
    AbstractThemeInterface,
)
from copick_shared_ui.widgets.cli.command_runner import (
    build_args,
    run_click_command_worker,
)
from copick_shared_ui.widgets.cli.param_widgets import ParamWidgetResult, create_param_widget


# Human-readable type names
_TYPE_DISPLAY = {
    "string": "text",
    "int": "integer",
    "float": "decimal",
    "bool": "flag",
    "choice": "choice",
    "path": "file path",
}


class _HelpPopup(QFrame):
    """Frameless popup that shows parameter documentation."""

    def __init__(self, text: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent, Qt.Popup)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            "QFrame { background: palette(window); border: 1px solid palette(mid); "
            "border-radius: 4px; padding: 6px; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextFormat(Qt.RichText)
        label.setMaximumWidth(320)
        layout.addWidget(label)

    def focusOutEvent(self, event):
        self.close()
        super().focusOutEvent(event)


def _build_help_html(param: ParamSchema) -> str:
    """Build rich-text content for the help popup."""
    parts = []

    if param.help:
        parts.append(param.help)

    meta = []
    type_name = _TYPE_DISPLAY.get(param.param_type, param.param_type)
    if param.choices:
        type_name = "choice: " + ", ".join(param.choices)
    meta.append(f"<b>Type:</b> {type_name}")

    if param.multiple:
        meta.append("<b>Multiple:</b> yes (comma-separated)")

    if param.default is not None and param.default != "" and not param.is_flag:
        meta.append(f"<b>Default:</b> {param.default}")
    elif param.is_flag:
        meta.append(f"<b>Default:</b> {'on' if param.default else 'off'}")

    if param.required and not param.is_flag:
        meta.append("<b>Required</b>")

    if meta:
        if parts:
            parts.append("")  # blank line separator
        parts.append("<br>".join(meta))

    return "<br>".join(parts)


def _make_param_label(param: ParamSchema) -> QWidget:
    """Create a form label row for a parameter with a clickable help button.

    Returns a widget containing the label text and, when help is available,
    a small '?' button that opens a popup overlay with the full description,
    expected type, and default value.
    """
    name = param.human_name
    if param.required and not param.is_flag:
        name = f"{name} *"

    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)

    label = QLabel(name)
    layout.addWidget(label)

    has_info = bool(param.help) or param.default is not None
    if has_info:
        help_btn = QToolButton()
        help_btn.setText("?")
        help_btn.setFixedSize(16, 16)
        help_btn.setStyleSheet(
            "QToolButton { color: #888; border: 1px solid #999; border-radius: 8px; "
            "font-size: 10px; font-weight: bold; padding: 0; }"
            "QToolButton:hover { color: #fff; background: #666; border-color: #666; }"
        )
        help_btn.setCursor(Qt.PointingHandCursor)

        html = _build_help_html(param)
        popup_ref = [None]  # mutable ref so the closure can toggle

        def _toggle_popup():
            if popup_ref[0] is not None and popup_ref[0].isVisible():
                popup_ref[0].close()
                popup_ref[0] = None
                return
            popup = _HelpPopup(html)
            popup_ref[0] = popup
            # Position below the button
            pos = help_btn.mapToGlobal(QPoint(0, help_btn.height() + 2))
            popup.move(pos)
            popup.show()

        help_btn.clicked.connect(_toggle_popup)
        layout.addWidget(help_btn)

    layout.addStretch()

    return container


class ClickCommandForm(QWidget):
    """Auto-generated form for a single Click CLI command.

    Builds the form layout from a CommandSchema, handles validation,
    runs the command in a background thread, and displays output.
    """

    command_completed = Signal(str)  # Emits category string after successful run

    def __init__(
        self,
        schema: CommandSchema,
        context_interface: AbstractCLIContextInterface,
        theme_interface: AbstractThemeInterface,
        refresh_interface: AbstractCLIRefreshInterface,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.schema = schema
        self.context = context_interface
        self.theme = theme_interface
        self.refresh = refresh_interface

        # Map: param_name -> (widget, get_value, set_value)
        self._param_widgets: Dict[str, Tuple[Any, Callable, Callable]] = {}
        self._active_worker = None

        self._build_ui()

        # Connect tree selection for URI pre-fill
        self.context.connect_selection_changed(self._on_tree_selection_changed)
        # Check if there's an initial selection
        self._try_prefill_from_selection(self.context.get_selected_copick_object())

    def _build_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        # Scrollable area for the form — vertical only
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        layout.setSpacing(8)

        # --- Header ---
        cmd_display = " ".join(self.schema.full_path)
        header_label = QLabel(f"<b>copick {cmd_display}</b>")
        layout.addWidget(header_label)

        if self.schema.short_help:
            help_label = QLabel(self.schema.short_help)
            help_label.setWordWrap(True)
            help_label.setStyleSheet("color: #888; margin-bottom: 4px;")
            layout.addWidget(help_label)

        # --- Arguments section (positional params) ---
        argument_params = [
            p for p in self.schema.params
            if p.is_argument and p.name not in _HIDDEN_PARAMS
        ]
        if argument_params:
            args_group = QGroupBox("Arguments")
            args_form = QFormLayout(args_group)
            args_form.setRowWrapPolicy(QFormLayout.WrapLongRows)
            args_form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
            for param in argument_params:
                widget, get_val, set_val = create_param_widget(
                    param, context=self.context, parent=self,
                )
                label = _make_param_label(param)
                args_form.addRow(label, widget)
                self._param_widgets[param.name] = (widget, get_val, set_val)
            layout.addWidget(args_group)

        # --- Option groups ---
        if self.schema.param_groups:
            for group in self.schema.param_groups:
                visible_params = [
                    p for p in group.params
                    if p.name not in _HIDDEN_PARAMS and not p.is_argument
                ]
                if not visible_params:
                    continue

                group_box = QGroupBox(group.name)
                form = QFormLayout(group_box)
                form.setRowWrapPolicy(QFormLayout.WrapLongRows)
                form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

                for param in visible_params:
                    widget, get_val, set_val = create_param_widget(
                        param, context=self.context, parent=self,
                    )
                    label = _make_param_label(param)
                    form.addRow(label, widget)
                    self._param_widgets[param.name] = (widget, get_val, set_val)

                layout.addWidget(group_box)
        else:
            # No groups — put all non-hidden, non-argument params in a single form
            option_params = [
                p for p in self.schema.params
                if p.name not in _HIDDEN_PARAMS and not p.is_argument
            ]
            if option_params:
                options_group = QGroupBox("Options")
                form = QFormLayout(options_group)
                form.setRowWrapPolicy(QFormLayout.WrapLongRows)
                form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
                for param in option_params:
                    widget, get_val, set_val = create_param_widget(
                        param, context=self.context, parent=self,
                    )
                    label = _make_param_label(param)
                    form.addRow(label, widget)
                    self._param_widgets[param.name] = (widget, get_val, set_val)
                layout.addWidget(options_group)

        # --- Buttons ---
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.run_btn = QPushButton("\u25b6 Run")
        self.run_btn.clicked.connect(self._on_run)
        btn_layout.addWidget(self.run_btn)

        # Add Dry Run button if the command has a --dry-run param
        has_dry_run = any(p.name == "dry_run" for p in self.schema.params)
        if has_dry_run:
            self.dry_run_btn = QPushButton("\u25b6 Dry Run")
            self.dry_run_btn.clicked.connect(self._on_dry_run)
            btn_layout.addWidget(self.dry_run_btn)

        self.reset_btn = QPushButton("\u21ba Reset Defaults")
        self.reset_btn.clicked.connect(self._reset_defaults)
        btn_layout.addWidget(self.reset_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # --- Progress indicator ---
        self.progress_widget = QWidget()
        progress_layout = QHBoxLayout(self.progress_widget)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        self.progress_label = QLabel("Running...")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_bar.setMaximumHeight(18)
        progress_layout.addWidget(self.progress_label)
        progress_layout.addWidget(self.progress_bar)
        self.progress_widget.setVisible(False)
        layout.addWidget(self.progress_widget)

        # --- Output panel ---
        self.output_label = QLabel("Output:")
        self.output_label.setVisible(False)
        layout.addWidget(self.output_label)

        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setMaximumHeight(200)
        self.output_text.setVisible(False)
        layout.addWidget(self.output_text)

        layout.addStretch()
        scroll.setWidget(scroll_content)
        outer_layout.addWidget(scroll)

    def _collect_values(self) -> Dict[str, Any]:
        """Collect current values from all parameter widgets."""
        values: Dict[str, Any] = {}
        for name, (widget, get_val, set_val) in self._param_widgets.items():
            values[name] = get_val()
        return values

    def _validate(self, values: Dict[str, Any]) -> Optional[str]:
        """Validate required fields. Returns error message or None."""
        for param in self.schema.params:
            if param.name in _HIDDEN_PARAMS:
                continue
            if param.required and not param.is_flag:
                val = values.get(param.name)
                if val is None or val == "" or val == []:
                    return f"Required field '{param.human_name}' is empty."
        return None

    def _on_run(self) -> None:
        """Execute the command."""
        self._execute(dry_run=False)

    def _on_dry_run(self) -> None:
        """Execute the command in dry-run mode."""
        self._execute(dry_run=True)

    def _execute(self, dry_run: bool = False) -> None:
        """Build args, validate, and run the command in background."""
        if self._active_worker is not None:
            return  # Already running

        values = self._collect_values()

        # Inject dry_run flag
        if dry_run:
            values["dry_run"] = True

        # Validate
        error = self._validate(values)
        if error:
            self._show_output(f"Validation error: {error}", is_error=True)
            return

        config_path = self.context.get_config_path()
        if config_path is None:
            self._show_output("Error: No copick config loaded.", is_error=True)
            return

        args = build_args(self.schema, values, config_path=config_path)
        command = self.schema.click_command

        # Show progress
        self.run_btn.setEnabled(False)
        self.progress_widget.setVisible(True)
        self.progress_label.setText("Running...")
        self.output_text.clear()
        self.output_text.setVisible(False)
        self.output_label.setVisible(False)

        # Launch background worker
        worker = run_click_command_worker(command, args)
        self._active_worker = worker

        worker.yielded.connect(self._on_progress)
        worker.returned.connect(self._on_finished)
        worker.errored.connect(self._on_error)
        worker.finished.connect(self._on_worker_done)
        worker.start()

    def _on_progress(self, message: str) -> None:
        """Handle progress messages from worker."""
        self.progress_label.setText(message)

    def _on_finished(self, result: tuple) -> None:
        """Handle command completion."""
        exit_code, output = result
        if exit_code == 0:
            self._show_output(output or "Command completed successfully.", is_error=False)
            # Trigger refresh
            self.refresh.refresh_after_command(self.schema.category)
            self.command_completed.emit(self.schema.category)
        else:
            self._show_output(
                f"Command failed (exit code {exit_code}):\n{output}",
                is_error=True,
            )

    def _on_error(self, exc: Exception) -> None:
        """Handle worker exception."""
        self._show_output(f"Error: {exc}", is_error=True)

    def _on_worker_done(self) -> None:
        """Clean up after worker finishes."""
        self._active_worker = None
        self.run_btn.setEnabled(True)
        self.progress_widget.setVisible(False)

    def _show_output(self, text: str, is_error: bool = False) -> None:
        """Display output text."""
        self.output_label.setVisible(True)
        self.output_text.setVisible(True)
        if is_error:
            self.output_text.setStyleSheet("color: #cc4444;")
        else:
            self.output_text.setStyleSheet("")
        self.output_text.setPlainText(text)

    def _reset_defaults(self) -> None:
        """Reset all widgets to their default values."""
        for param in self.schema.params:
            if param.name in _HIDDEN_PARAMS:
                continue
            if param.name in self._param_widgets:
                _, _, set_val = self._param_widgets[param.name]
                set_val(param.default)
        self.output_text.clear()
        self.output_text.setVisible(False)
        self.output_label.setVisible(False)

    def _on_tree_selection_changed(self, copick_obj: Any) -> None:
        """Handle tree selection change — pre-fill matching URI fields."""
        self._try_prefill_from_selection(copick_obj)

    def _try_prefill_from_selection(self, copick_obj: Any) -> None:
        """Pre-fill URI widgets and run name from the selected copick object."""
        if copick_obj is None:
            return

        # Determine object type from copick model class
        obj_type = self._get_copick_object_type(copick_obj)
        if obj_type is None:
            return

        # Serialize to URI
        try:
            from copick.util.uri import serialize_copick_uri
            uri = serialize_copick_uri(copick_obj)
        except Exception:
            return

        # Extract and pre-fill run name
        try:
            run_name = None
            if hasattr(copick_obj, "run") and copick_obj.run is not None:
                run_name = copick_obj.run.name
            elif hasattr(copick_obj, "voxel_spacing") and hasattr(copick_obj.voxel_spacing, "run"):
                run_name = copick_obj.voxel_spacing.run.name
            if run_name:
                self.prefill_run_name(run_name)
        except Exception:
            pass

        # Fill matching input/reference URI widgets
        for param in self.schema.params:
            if param.uri_meta is None:
                continue
            if param.uri_meta.role == "output":
                continue  # Don't overwrite output URIs
            if param.uri_meta.object_type not in (obj_type, "any"):
                continue
            if param.name in self._param_widgets:
                _, _, set_val = self._param_widgets[param.name]
                set_val(uri)

    @staticmethod
    def _get_copick_object_type(copick_obj: Any) -> Optional[str]:
        """Map a copick model object to its URI object type string."""
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

    def prefill_uri(self, uri: str, object_type: str = "") -> None:
        """Pre-fill a URI widget matching the given object type.

        When object_type is provided, only fills fields whose uri_meta.object_type
        matches (or is "any"). This prevents e.g. a tomogram URI from being
        stuffed into a picks input field.

        Called externally by the context menu.
        """
        for param in self.schema.params:
            if param.uri_meta is None:
                continue
            if param.uri_meta.role == "output":
                continue
            if object_type and param.uri_meta.object_type not in (object_type, "any"):
                continue
            if param.name in self._param_widgets:
                _, _, set_val = self._param_widgets[param.name]
                set_val(uri)
                return

    def prefill_run_name(self, run_name: str) -> None:
        """Pre-fill run name / run_names fields with the given run name.

        Called externally by the context menu so the tool operates on
        the same run the selected annotation belongs to.
        """
        for param in self.schema.params:
            if param.auto_fill_type in ("run_names",) or param.name in ("run", "run_names"):
                if param.name in self._param_widgets:
                    _, _, set_val = self._param_widgets[param.name]
                    set_val(run_name)
                    return

    def cleanup(self) -> None:
        """Stop any active worker and disconnect signals."""
        self.context.disconnect_selection_changed(self._on_tree_selection_changed)
        if self._active_worker is not None and hasattr(self._active_worker, "quit"):
            self._active_worker.quit()
            self._active_worker = None
