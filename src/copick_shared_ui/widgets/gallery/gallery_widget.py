"""Platform-agnostic gallery widget for displaying copick runs."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from qtpy.QtCore import Qt, Signal, Slot
from qtpy.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget

from copick_shared_ui.core.models import (
    AbstractImageInterface,
    AbstractSessionInterface,
    AbstractThemeInterface,
    AbstractWorkerInterface,
)
from copick_shared_ui.widgets.gallery.run_card import RunCard

if TYPE_CHECKING:
    from copick.models import CopickRun


class CopickGalleryWidget(QWidget):
    """Platform-agnostic gallery widget displaying copick runs in a grid with thumbnails."""

    run_selected = Signal(object)  # Emits selected run
    info_requested = Signal(object)  # Emits run for info view

    def __init__(
        self,
        session_interface: AbstractSessionInterface,
        theme_interface: AbstractThemeInterface,
        worker_interface: AbstractWorkerInterface,
        image_interface: AbstractImageInterface,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)

        # Platform interfaces
        self.session_interface = session_interface
        self.theme_interface = theme_interface
        self.worker_interface = worker_interface
        self.image_interface = image_interface

        # Data
        self.copick_root: Optional[Any] = None
        self.runs: List["CopickRun"] = []
        self.filtered_runs: List["CopickRun"] = []
        self.all_run_cards: Dict[str, RunCard] = {}  # run_name -> RunCard (persistent cache)
        self.visible_run_cards: Dict[str, RunCard] = {}  # run_name -> RunCard (currently visible)
        self.search_filter: str = ""
        self.thumbnail_cache: Dict[str, Any] = {}  # run_name -> pixmap (thumbnail cache)
        self._grid_dirty: bool = True  # Flag to track if grid needs updating (data path)
        # Last column count the grid was laid out at. Resize only reflows when this
        # changes (mirrors info_widget._tomo_grid_last_cols); None forces a first layout.
        self._grid_last_cols: Optional[int] = None

        # Track widget lifecycle
        self._is_destroyed: bool = False

        self._setup_ui()
        self._apply_styling()

        # Connect to theme change events
        self.theme_interface.connect_theme_changed(self._on_theme_changed)

    def _setup_ui(self) -> None:
        """Setup the gallery UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Header
        header_layout = QHBoxLayout()

        title_label = QLabel("📸 Run Gallery", objectName="gallery_title_label")
        # Word-wrap so the title collapses to its widest word instead of pinning a
        # ~150px minimum on the header (which sits outside the scroll area).
        title_label.setWordWrap(True)
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        # Regenerate thumbnails button — icon-only so the header stays narrow on
        # small screens (the action is described by the tooltip).
        self.regenerate_button = QPushButton("🔄", objectName="regenerate_thumbnails_button")
        self.regenerate_button.setToolTip("Clear cache and regenerate all thumbnails")
        self.regenerate_button.clicked.connect(self._on_regenerate_thumbnails)
        header_layout.addWidget(self.regenerate_button)

        # Search box — allow it to shrink on narrow docks instead of pinning a
        # fixed 200px width; cap it so it does not hog the header in wide views.
        self.search_box = QLineEdit(objectName="gallery_search_input")
        self.search_box.setPlaceholderText("Search runs...")
        self.search_box.setMinimumWidth(80)
        self.search_box.setMaximumWidth(200)
        self.search_box.textChanged.connect(self._on_search_changed)
        header_layout.addWidget(self.search_box)

        layout.addLayout(header_layout)

        # Scroll area for grid
        self.scroll_area = QScrollArea(objectName="gallery_scroll_area")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        layout.addWidget(self.scroll_area)

        # Grid widget
        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setSpacing(15)
        self.grid_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.scroll_area.setWidget(self.grid_widget)

        # Empty state label
        self.empty_label = QLabel("No runs to display", objectName="gallery_empty_state_label")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setVisible(False)
        layout.addWidget(self.empty_label)

    def delete(self) -> None:
        """Clean up widget resources."""
        if self._is_destroyed:
            return

        self._is_destroyed = True

        # Clear workers
        self.worker_interface.shutdown_workers(timeout_ms=3000)

        # Clear caches
        self.all_run_cards.clear()
        self.visible_run_cards.clear()
        self.thumbnail_cache.clear()

    def set_copick_root(self, copick_root: Optional[Any]) -> None:
        """Set the copick root and load runs."""
        # Clear workers to cancel any pending thumbnail loads from previous session
        self.worker_interface.clear_workers()

        # Clear caches when root changes
        self.all_run_cards.clear()
        self.visible_run_cards.clear()
        self.thumbnail_cache.clear()
        self._grid_dirty = True
        self._grid_last_cols = None  # new run set -> force a fresh layout

        self.copick_root = copick_root
        if copick_root:
            self.runs = list(copick_root.runs)
            self.filtered_runs = self.runs.copy()
            self._update_grid()
        else:
            self.runs = []
            self.filtered_runs = []
            self._clear_grid()

    def apply_search_filter(self, filter_text: str) -> None:
        """Apply search filter from external source (like tree widget)."""
        self.search_filter = filter_text.lower()
        self.search_box.setText(filter_text)  # Update search box
        self._filter_runs()
        self._update_grid()

    @Slot(str)
    def _on_search_changed(self, text: str):
        """Handle search box text change."""
        self.search_filter = text.lower()
        self._filter_runs()
        self._update_grid()

    def _filter_runs(self) -> None:
        """Filter runs based on search text."""
        old_filtered = {run.name for run in self.filtered_runs}

        if not self.search_filter:
            self.filtered_runs = self.runs.copy()
        else:
            self.filtered_runs = [run for run in self.runs if self.search_filter in run.name.lower()]

        # Check if filtering actually changed the results
        new_filtered = {run.name for run in self.filtered_runs}
        self._grid_dirty = old_filtered != new_filtered

    def _clear_grid(self) -> None:
        """Clear all cards from the grid layout (but keep them cached)."""
        # Remove all cards from layout but don't delete them
        for i in reversed(range(self.grid_layout.count())):
            child = self.grid_layout.itemAt(i).widget()
            if child:
                # Temporarily reparent to None to remove from layout without deleting
                child.setParent(None)

        self.visible_run_cards.clear()
        self.empty_label.setVisible(True)
        self.grid_widget.setVisible(False)

    def _compute_cards_per_row(self) -> int:
        """Number of card columns that fit the current scroll-area width.

        Derived from the scroll area (not self.width()) so the resize guard in
        _reflow_grid compares against the same width the layout uses. 235 = 220px
        fixed card width + 15px grid spacing; 30 leaves room for margins/scrollbar.
        """
        return max(1, (self.scroll_area.width() - 30) // 235)

    def _update_grid(self) -> None:
        """Update the grid with current filtered runs using cached cards."""
        if self._is_destroyed:
            return

        # Only update if grid is dirty
        if not self._grid_dirty:
            return

        # Clear existing grid layout (but keep cards cached)
        self._clear_grid()

        if not self.filtered_runs:
            self.empty_label.setVisible(True)
            self.grid_widget.setVisible(False)
            self._grid_last_cols = None
            return

        self.empty_label.setVisible(False)
        self.grid_widget.setVisible(True)

        # Calculate grid dimensions
        cards_per_row = self._compute_cards_per_row()

        # Add cards for filtered runs (reuse cached cards where possible)
        for i, run in enumerate(self.filtered_runs):
            row = i // cards_per_row
            col = i % cards_per_row

            # Check if we already have this card cached
            if run.name in self.all_run_cards:
                # Reuse existing card
                card = self.all_run_cards[run.name]
            else:
                # Create new card
                card = RunCard(run, self.theme_interface, self.image_interface)
                card.clicked.connect(self._on_run_card_clicked)
                card.info_requested.connect(self._on_run_info_requested)
                self.all_run_cards[run.name] = card

                # Check if we have a cached thumbnail in memory first
                if run.name in self.thumbnail_cache:
                    cached_thumbnail = self.thumbnail_cache[run.name]
                    card.set_thumbnail(cached_thumbnail)
                else:
                    # Start thumbnail loading - let the worker check disk cache
                    self._load_run_thumbnail(run, run.name)

            # Add to visible cards and grid layout
            self.visible_run_cards[run.name] = card
            self.grid_layout.addWidget(card, row, col)

        # Mark grid as clean and remember the column count so a subsequent resize
        # that does not change it can skip the reflow entirely.
        self._grid_dirty = False
        self._grid_last_cols = cards_per_row

    def _load_run_thumbnail(self, run: "CopickRun", thumbnail_id: str, force_regenerate: bool = False) -> None:
        """Start async loading of run thumbnail."""
        if self._is_destroyed:
            return

        # Skip expensive tomogram count logging to prevent UI blocking with large datasets
        self.worker_interface.start_thumbnail_worker(run, thumbnail_id, self._on_thumbnail_loaded, force_regenerate)

    def _on_thumbnail_loaded(self, thumbnail_id: str, pixmap: Optional[Any], error: Optional[str]) -> None:
        """Handle thumbnail loading completion."""

        if self._is_destroyed or thumbnail_id not in self.all_run_cards:
            return

        card = self.all_run_cards[thumbnail_id]

        if error:
            card.set_error(error)
        else:
            card.set_thumbnail(pixmap)
            # Cache the thumbnail for future use
            if pixmap:
                self.thumbnail_cache[thumbnail_id] = pixmap

    @Slot(object)
    def _on_run_card_clicked(self, run: "CopickRun") -> None:
        """Handle run card click - switch to 3D view and emit signal."""
        try:
            # Switch to 3D view
            self.session_interface.switch_to_3d_view()

            # Emit signal for handling tomogram loading
            self.run_selected.emit(run)

        except Exception:
            # Still emit the signal as fallback
            self.run_selected.emit(run)

    @Slot(object)
    def _on_run_info_requested(self, run: "CopickRun") -> None:
        """Handle run info button click."""
        self.info_requested.emit(run)

    def _apply_styling(self) -> None:
        """Apply theme-aware styling to all components."""
        # Apply main stylesheet
        self.setStyleSheet(self.theme_interface.get_theme_stylesheet())

        colors = self.theme_interface.get_theme_colors()

        # Gallery-specific styles
        gallery_styles = f"""
            QLabel[objectName="gallery_title_label"] {{
                color: {colors['text_primary']};
                font-size: 18px;
                font-weight: bold;
                padding: 8px;
            }}

            QLabel[objectName="gallery_empty_state_label"] {{
                color: {colors['text_muted']};
                font-size: 14px;
                padding: 40px;
            }}

            QScrollArea[objectName="gallery_scroll_area"] {{
                border: none;
                background-color: {colors['bg_primary']};
            }}

            RunCard {{
                background-color: {colors['bg_tertiary']};
                border: 1px solid {colors['border_secondary']};
                border-radius: 8px;
            }}

            RunCard:hover {{
                border: 2px solid {colors['border_accent']};
                background-color: {colors['bg_quaternary']};
            }}
        """

        # Apply combined styles
        self.setStyleSheet(self.theme_interface.get_theme_stylesheet() + gallery_styles)

        # Apply button styles
        self.regenerate_button.setStyleSheet(self.theme_interface.get_button_stylesheet("accent"))

        # Apply input styles
        self.search_box.setStyleSheet(self.theme_interface.get_input_stylesheet())

    def _on_theme_changed(self) -> None:
        """Handle theme change by reapplying styles."""
        self._apply_styling()

        # Update all existing run cards
        for card in self.all_run_cards.values():
            card.refresh_theme()

    @Slot()
    def _on_regenerate_thumbnails(self) -> None:
        """Handle regenerate thumbnails button click."""
        # Clear memory cache
        self.thumbnail_cache.clear()

        # Reset all cards to loading state
        for card in self.all_run_cards.values():
            card.set_loading("Regenerating...")

        # Force regenerate all visible thumbnails
        for run in self.filtered_runs:
            if run.name in self.all_run_cards:
                self._load_run_thumbnail(run, run.name, force_regenerate=True)

    def _reflow_grid(self) -> None:
        """Reposition already-visible cards into a new column count on resize.

        This is the cheap resize path (mirrors info_widget._reflow_tomo_grids):
        it never recreates cards, never toggles grid visibility, and early-returns
        when the column count is unchanged -- so the vast majority of drag-resize
        events (which do not cross a ~235px column threshold) do no work at all.
        """
        if self._is_destroyed or not self.visible_run_cards:
            return

        cols = self._compute_cards_per_row()
        # resizeEvent fires on every pixel; only relayout when the column count
        # actually changes (the grid is otherwise byte-for-byte identical because
        # RunCard is a fixed size).
        if cols == self._grid_last_cols:
            return
        # DEBUG: fires only when the column count actually changes -- during a drag
        # this should print rarely (once per ~235px), confirming resize is now a
        # no-op on the common path. Remove once verified.
        print(f"🔧 Gallery: reflowing grid {self._grid_last_cols} -> {cols} cols ({len(self.visible_run_cards)} cards)")
        self._grid_last_cols = cols

        # Preserve on-screen order (filtered_runs order, as populated by _update_grid).
        cards = [self.all_run_cards[run.name] for run in self.filtered_runs if run.name in self.all_run_cards]

        # Batch repaints at the viewport (grid_widget's parent, so it also covers
        # the scrollbar) so the intermediate detached state is never painted;
        # finally guarantees re-enable even if a card was deleted underneath us.
        viewport = self.scroll_area.viewport()
        viewport.setUpdatesEnabled(False)
        try:
            # removeWidget (not setParent(None)) repositions without reparenting or
            # hiding the card, which is what causes the resize flicker today.
            for card in cards:
                self.grid_layout.removeWidget(card)
            for i, card in enumerate(cards):
                self.grid_layout.addWidget(card, i // cols, i % cols)
        except RuntimeError:
            # A cached card was deleted underneath us; force a full rebuild below.
            self._grid_last_cols = None
            self._grid_dirty = True
        finally:
            viewport.setUpdatesEnabled(True)

        if self._grid_dirty:
            self._update_grid()

    def resizeEvent(self, event: Any) -> None:  # noqa: N802 (Qt override)
        """Handle widget resize by reflowing the grid only when the column count changes.

        The heavy _update_grid teardown/rebuild is intentionally NOT run here; the
        data path (set_copick_root / search filter) owns that. _reflow_grid just
        repositions the cached cards in place and no-ops on an unchanged column
        count, so a continuous drag-resize does almost no work and does not flicker.
        """
        super().resizeEvent(event)
        self._reflow_grid()
