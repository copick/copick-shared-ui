"""Categorized command browser widget for copick CLI tools.

Provides a searchable, categorized list of all discovered Click commands
with an auto-generated form panel for the selected command.
"""

from typing import Dict, List, Optional

try:
    from qtpy.QtCore import Qt
    from qtpy.QtWidgets import (
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QSplitter,
        QTreeWidget,
        QTreeWidgetItem,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    from Qt.QtCore import Qt
    from Qt.QtWidgets import (
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QSplitter,
        QTreeWidget,
        QTreeWidgetItem,
        QVBoxLayout,
        QWidget,
    )

from copick_shared_ui.core.click_schema import CommandSchema, discover_commands_by_category
from copick_shared_ui.core.models import (
    AbstractCLIContextInterface,
    AbstractCLIRefreshInterface,
    AbstractThemeInterface,
    AbstractWorkerInterface,
)
from copick_shared_ui.widgets.cli.command_form import ClickCommandForm

# Preferred display order for categories
_CATEGORY_ORDER = [
    "Data Management",
    "Data Processing",
    "Utilities",
    "Other",
]


class ClickCommandBrowser(QWidget):
    """Top-level widget that lists all CLI commands and shows a form for the selected one.

    Layout:
        - Left panel: categorized, searchable command tree
        - Right panel: auto-generated ClickCommandForm for the selected command
    """

    def __init__(
        self,
        context_interface: AbstractCLIContextInterface,
        theme_interface: AbstractThemeInterface,
        worker_interface: AbstractWorkerInterface,
        refresh_interface: AbstractCLIRefreshInterface,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.context = context_interface
        self.theme = theme_interface
        self.worker = worker_interface
        self.refresh = refresh_interface

        self._commands_by_category: Dict[str, List[CommandSchema]] = {}
        self._all_schemas: List[CommandSchema] = []
        self._current_form: Optional[ClickCommandForm] = None
        # Map tree items to schemas
        self._item_to_schema: Dict[int, CommandSchema] = {}

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Main splitter
        self.splitter = QSplitter(Qt.Horizontal)

        # --- Left panel: command list ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        # Search bar
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Search tools...")
        self.search_field.setClearButtonEnabled(True)
        self.search_field.textChanged.connect(self._filter_commands)
        left_layout.addWidget(self.search_field)

        # Command tree
        self.command_tree = QTreeWidget()
        self.command_tree.setHeaderHidden(True)
        self.command_tree.setIndentation(16)
        self.command_tree.itemClicked.connect(self._on_command_selected)
        left_layout.addWidget(self.command_tree)

        self.splitter.addWidget(left_panel)

        # --- Right panel: form area ---
        self.form_container = QWidget()
        self.form_layout = QVBoxLayout(self.form_container)
        self.form_layout.setContentsMargins(4, 0, 0, 0)

        # Empty state
        self.empty_label = QLabel(
            "Select a tool from the list to configure and run it.\n\n"
            "Tools are auto-discovered from installed copick packages."
        )
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("color: #888; font-size: 13px; padding: 40px;")
        self.empty_label.setWordWrap(True)
        self.form_layout.addWidget(self.empty_label)

        self.splitter.addWidget(self.form_container)

        # Set initial sizes (30% list, 70% form)
        self.splitter.setSizes([250, 550])

        layout.addWidget(self.splitter)

    def populate_commands(self) -> None:
        """Discover and display all available CLI commands."""
        self._commands_by_category = discover_commands_by_category()
        self._all_schemas = []
        for schemas in self._commands_by_category.values():
            self._all_schemas.extend(schemas)
        self._rebuild_tree()

    def _rebuild_tree(self, filter_text: str = "") -> None:
        """Rebuild the command tree, optionally filtering by search text."""
        self.command_tree.clear()
        self._item_to_schema.clear()
        filter_lower = filter_text.lower()

        for category in _CATEGORY_ORDER:
            schemas = self._commands_by_category.get(category, [])
            if not schemas:
                continue

            # Group commands by their parent group (first element of full_path)
            # e.g. ["convert", "picks2seg"] -> group "convert"
            subgroups: Dict[str, List[CommandSchema]] = {}
            top_level: List[CommandSchema] = []

            for schema in schemas:
                if len(schema.full_path) > 1:
                    group_name = schema.full_path[0]
                    subgroups.setdefault(group_name, []).append(schema)
                else:
                    top_level.append(schema)

            # Filter
            filtered_top = [
                s for s in top_level
                if not filter_lower or filter_lower in s.name.lower() or filter_lower in s.short_help.lower()
            ]
            filtered_subgroups: Dict[str, List[CommandSchema]] = {}
            for gname, gschemas in subgroups.items():
                filtered = [
                    s for s in gschemas
                    if not filter_lower
                    or filter_lower in s.name.lower()
                    or filter_lower in s.short_help.lower()
                    or filter_lower in gname.lower()
                ]
                if filtered:
                    filtered_subgroups[gname] = filtered

            if not filtered_top and not filtered_subgroups:
                continue

            # Category item
            cat_item = QTreeWidgetItem(self.command_tree, [category])
            cat_item.setFlags(cat_item.flags() & ~Qt.ItemIsSelectable)
            font = cat_item.font(0)
            font.setBold(True)
            cat_item.setFont(0, font)

            # Top-level commands
            for schema in sorted(filtered_top, key=lambda s: s.name):
                cmd_item = QTreeWidgetItem(cat_item, [schema.name])
                cmd_item.setToolTip(0, schema.short_help)
                self._item_to_schema[id(cmd_item)] = schema

            # Subgroups
            for gname in sorted(filtered_subgroups.keys()):
                group_item = QTreeWidgetItem(cat_item, [gname])
                group_item.setFlags(group_item.flags() & ~Qt.ItemIsSelectable)
                font = group_item.font(0)
                font.setItalic(True)
                group_item.setFont(0, font)

                for schema in sorted(filtered_subgroups[gname], key=lambda s: s.name):
                    cmd_item = QTreeWidgetItem(group_item, [schema.name])
                    cmd_item.setToolTip(0, schema.short_help)
                    self._item_to_schema[id(cmd_item)] = schema

            cat_item.setExpanded(True)
            # Expand subgroups too if filtering
            if filter_lower:
                for i in range(cat_item.childCount()):
                    child = cat_item.child(i)
                    child.setExpanded(True)

        # Also handle any categories not in the preferred order
        for category, schemas in self._commands_by_category.items():
            if category in _CATEGORY_ORDER:
                continue
            filtered = [
                s for s in schemas
                if not filter_lower or filter_lower in s.name.lower() or filter_lower in s.short_help.lower()
            ]
            if not filtered:
                continue

            cat_item = QTreeWidgetItem(self.command_tree, [category])
            cat_item.setFlags(cat_item.flags() & ~Qt.ItemIsSelectable)
            font = cat_item.font(0)
            font.setBold(True)
            cat_item.setFont(0, font)

            for schema in sorted(filtered, key=lambda s: s.name):
                cmd_item = QTreeWidgetItem(cat_item, [schema.name])
                cmd_item.setToolTip(0, schema.short_help)
                self._item_to_schema[id(cmd_item)] = schema

            cat_item.setExpanded(True)

    def _filter_commands(self, text: str) -> None:
        """Filter the command tree by search text."""
        self._rebuild_tree(filter_text=text)

    def _on_command_selected(self, item: QTreeWidgetItem, column: int) -> None:
        """Handle command selection in the tree."""
        schema = self._item_to_schema.get(id(item))
        if schema is None:
            return  # Clicked on a category or group header

        self._show_form(schema)

    def _show_form(self, schema: CommandSchema) -> None:
        """Display the form for the given command schema."""
        # Clean up existing form
        if self._current_form is not None:
            self._current_form.cleanup()
            self.form_layout.removeWidget(self._current_form)
            self._current_form.deleteLater()
            self._current_form = None

        # Hide empty state
        self.empty_label.setVisible(False)

        # Create new form
        form = ClickCommandForm(
            schema=schema,
            context_interface=self.context,
            theme_interface=self.theme,
            refresh_interface=self.refresh,
            parent=self,
        )
        self.form_layout.addWidget(form)
        self._current_form = form

    def cleanup(self) -> None:
        """Clean up resources."""
        if self._current_form is not None:
            self._current_form.cleanup()
