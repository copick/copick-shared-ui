"""Platform-agnostic info widget for displaying detailed copick run information."""

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from qtpy.QtCore import Qt, Signal, Slot
from qtpy.QtGui import QFont
from qtpy.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from copick_shared_ui.core.models import (
    AbstractImageInterface,
    AbstractInfoSessionInterface,
    AbstractThemeInterface,
    AbstractWorkerInterface,
)

if TYPE_CHECKING:
    from copick.models import CopickRun, CopickTomogram, CopickVoxelSpacing


class CopickInfoWidget(QWidget):
    """Platform-agnostic widget for displaying detailed copick run information."""

    tomogram_clicked = Signal(object)  # Emits tomogram when clicked

    def __init__(
        self,
        session_interface: AbstractInfoSessionInterface,
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
        self.current_run: Optional["CopickRun"] = None
        self.current_run_name: Optional[str] = None
        self._loading_states: Dict[str, str] = {}
        self._loaded_data: Dict[str, List[Any]] = {}

        # Track widget lifecycle
        self._is_destroyed: bool = False

        # Thumbnail cache and widgets
        self._thumbnails: Dict[str, Any] = {}
        self._thumbnail_widgets: Dict[str, QFrame] = {}

        self._setup_ui()
        self._apply_styling()

        # Connect to theme change events
        self.theme_interface.connect_theme_changed(self._on_theme_changed)

    def delete(self) -> None:
        """Clean up widget resources."""
        if self._is_destroyed:
            return

        self._is_destroyed = True

        # Clear workers
        self.worker_interface.shutdown_workers(timeout_ms=3000)

        # Clear caches
        self._thumbnails.clear()
        self._thumbnail_widgets.clear()
        self._loaded_data.clear()
        self._loading_states.clear()

    def _setup_ui(self) -> None:
        """Set up the UI components."""
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # Header section - fixed size
        self._create_header(layout)

        # Scrollable content area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameStyle(QFrame.NoFrame)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Content widget inside scroll area
        self._content_widget = QWidget()
        self._content_layout = QVBoxLayout()
        self._content_layout.setContentsMargins(10, 10, 10, 10)
        self._content_layout.setSpacing(12)
        self._content_layout.setAlignment(Qt.AlignTop)
        self._content_widget.setLayout(self._content_layout)
        self._content_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        scroll_area.setWidget(self._content_widget)
        layout.addWidget(scroll_area, 1)

        # Footer hint - fixed size
        self._create_footer(layout)

        self.setLayout(layout)

    def _create_header(self, layout: QVBoxLayout) -> None:
        """Create the header section."""
        header_widget = QWidget()
        header_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        header_layout = QVBoxLayout()
        header_layout.setContentsMargins(10, 10, 10, 15)
        header_layout.setSpacing(8)
        header_layout.setAlignment(Qt.AlignCenter)

        # Top row with back button and title
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(10)

        # Back to gallery button
        self._back_to_gallery_button = QPushButton("📸 Back to Gallery")
        self._back_to_gallery_button.setToolTip("Return to gallery view")
        self._back_to_gallery_button.clicked.connect(self._on_back_to_gallery)

        # Title
        title_label = QLabel("Copick Run Details")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # Add to top row
        top_row.addWidget(self._back_to_gallery_button)
        top_row.addStretch()
        top_row.addWidget(title_label)
        top_row.addStretch()

        # Add invisible placeholder widget to balance the button on the left
        placeholder = QWidget()
        placeholder.setFixedSize(self._back_to_gallery_button.sizeHint())
        top_row.addWidget(placeholder)

        header_layout.addLayout(top_row)

        # Run name
        self._run_name_label = QLabel("No run selected")
        name_font = QFont()
        name_font.setPointSize(18)
        name_font.setBold(True)
        self._run_name_label.setFont(name_font)
        self._run_name_label.setAlignment(Qt.AlignCenter)
        self._run_name_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        header_layout.addWidget(self._run_name_label)

        header_widget.setLayout(header_layout)
        layout.addWidget(header_widget, 0)

    def _create_footer(self, layout: QVBoxLayout) -> None:
        """Create the footer hint."""
        footer_label = QLabel("💡 Click on tomogram cards to load them in the viewer")
        footer_label.setAlignment(Qt.AlignCenter)
        footer_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.footer_label = footer_label
        layout.addWidget(footer_label, 0)

    def _apply_styling(self) -> None:
        """Apply theme-aware styling to all components."""
        # Apply main stylesheet
        self.setStyleSheet(self.theme_interface.get_theme_stylesheet())

        # Apply button styling
        self._back_to_gallery_button.setStyleSheet(self.theme_interface.get_button_stylesheet("primary"))

        # Apply theme-aware styling to run name label
        colors = self.theme_interface.get_theme_colors()
        self._run_name_label.setStyleSheet(f"color: {colors['accent_primary']}; margin-bottom: 5px;")

        # Apply footer styling
        self._apply_footer_styling()

    def _apply_footer_styling(self) -> None:
        """Apply theme-aware styling to footer."""
        if hasattr(self, "footer_label"):
            colors = self.theme_interface.get_theme_colors()
            self.footer_label.setStyleSheet(
                f"""
                QLabel {{
                    background-color: {colors['bg_secondary']};
                    border-radius: 6px;
                    padding: 10px;
                    font-size: 10px;
                    color: {colors['text_muted']};
                }}
            """,
            )

    def _on_theme_changed(self) -> None:
        """Handle theme change by reapplying styles."""
        self._apply_styling()

    def set_run(self, run: Optional["CopickRun"]) -> None:
        """Set the current run object and start async loading."""
        if self._is_destroyed:
            return

        self.current_run = run
        if run:
            self.current_run_name = run.name
            # Clear previous data and loading states
            self._loaded_data.clear()
            self._loading_states.clear()

            # Start async loading of all data types
            self._start_async_loading()
        else:
            self.current_run_name = None
            self._loaded_data.clear()
            self._loading_states.clear()

        self._update_display()

    def _start_async_loading(self) -> None:
        """Start asynchronous loading of all run data."""
        if not self.current_run or self._is_destroyed:
            return

        data_types = ["voxel_spacings", "tomograms", "picks", "meshes", "segmentations"]

        for data_type in data_types:
            if data_type not in self._loading_states:
                self._loading_states[data_type] = "loading"
                # Start async data loading using worker interface
                self._start_data_loading_worker(data_type)

    def _start_data_loading_worker(self, data_type: str) -> None:
        """Start a data loading worker for the specified data type."""
        if not self.current_run or self._is_destroyed:
            return

        # Use the worker interface to start threaded data loading
        self.worker_interface.start_data_worker(
            run=self.current_run,
            data_type=data_type,
            callback=self._handle_data_loaded,
        )

    def _handle_data_loaded(self, data_type: str, data: Optional[List[Any]], error: Optional[str]) -> None:
        """Handle data loading completion."""
        if self._is_destroyed:
            print(f"⚠️ InfoWidget: Widget destroyed, ignoring data for '{data_type}'")
            return

        if error:
            print(f"❌ InfoWidget: Error loading '{data_type}': {error}")
            self._loading_states[data_type] = f"error: {error}"
        else:
            self._loading_states[data_type] = "loaded"
            self._loaded_data[data_type] = data or []

        # Update display
        self._update_display()

    @Slot()
    def _update_display(self) -> None:
        """Update the widget display."""
        # Update run name
        run_display = self.current_run_name or "No run selected"
        self._run_name_label.setText(run_display)

        # Clear existing content
        while self._content_layout.count():
            child = self._content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Clear thumbnail widget references since widgets are being deleted
        self._thumbnail_widgets.clear()

        if self.current_run:
            # Add voxel spacings section with nested tomograms
            self._add_voxel_spacings_section()

            # Add annotations group (picks, meshes, segmentations)
            self._add_annotations_section()
        else:
            # Show empty state
            empty_label = QLabel("Select a run from the copick tree to view its contents.")
            empty_label.setAlignment(Qt.AlignCenter)
            colors = self.theme_interface.get_theme_colors()
            empty_label.setStyleSheet(f"color: {colors['text_muted']}; font-style: italic; padding: 40px;")
            self._content_layout.addWidget(empty_label)

    def _add_voxel_spacings_section(self) -> None:
        """Add the voxel spacings section with nested tomograms."""
        voxel_status = self._loading_states.get("voxel_spacings", "not_started")
        tomo_status = self._loading_states.get("tomograms", "not_started")

        # Create section frame
        section_frame = self._create_section_frame()
        section_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        section_layout = QVBoxLayout()
        section_layout.setContentsMargins(15, 15, 15, 15)
        section_layout.setSpacing(12)

        # Section header
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)

        title_label = QLabel("📏 Voxel Spacings & Tomograms")
        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        header_layout.addWidget(title_label)

        # Status indicator
        if voxel_status == "loading" or tomo_status == "loading":
            status_label = self._create_status_label("loading", "")
            status_label.setText("Loading...")
        elif voxel_status == "loaded" and tomo_status == "loaded":
            vs_count = len(self._loaded_data.get("voxel_spacings", []))
            tomo_count = len(self._loaded_data.get("tomograms", []))
            status_label = self._create_status_label("loaded", "")
            status_label.setText(f"✓ {vs_count} voxel spacings, {tomo_count} tomograms")
        elif voxel_status.startswith("error:") or tomo_status.startswith("error:"):
            status_label = self._create_status_label("error: Combined data error", "")
            status_label.setText("✗ Error loading data")
        else:
            status_label = self._create_status_label("pending", "")
            status_label.setText("Pending...")

        status_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        header_layout.addStretch()
        header_layout.addWidget(status_label)

        section_layout.addLayout(header_layout)

        # Content
        if voxel_status == "loaded" and tomo_status == "loaded" and "voxel_spacings" in self._loaded_data:
            voxel_spacings = self._loaded_data["voxel_spacings"]
            tomograms = self._loaded_data.get("tomograms", [])

            if voxel_spacings:
                content_widget = self._create_nested_voxel_tomogram_content(voxel_spacings, tomograms)
                content_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                section_layout.addWidget(content_widget)
            else:
                empty_label = QLabel("No voxel spacings found")
                empty_label.setAlignment(Qt.AlignCenter)
                empty_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                colors = self.theme_interface.get_theme_colors()
                empty_label.setStyleSheet(f"color: {colors['text_muted']}; font-style: italic; padding: 15px;")
                section_layout.addWidget(empty_label)
        else:
            # Show loading placeholder
            if voxel_status == "loading" or tomo_status == "loading":
                content_label = self._create_content_placeholder("loading")
            elif voxel_status.startswith("error:") or tomo_status.startswith("error:"):
                content_label = self._create_content_placeholder("error: Failed to load data")
            else:
                content_label = self._create_content_placeholder("pending")
            content_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            section_layout.addWidget(content_label)

        section_frame.setLayout(section_layout)
        self._content_layout.addWidget(section_frame)

    def _add_annotations_section(self) -> None:
        """Add the annotations group section."""
        picks_status = self._loading_states.get("picks", "not_started")
        meshes_status = self._loading_states.get("meshes", "not_started")
        seg_status = self._loading_states.get("segmentations", "not_started")

        # Create section frame
        section_frame = self._create_section_frame()
        section_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        section_layout = QVBoxLayout()
        section_layout.setContentsMargins(15, 15, 15, 15)
        section_layout.setSpacing(12)

        # Section header
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)

        title_label = QLabel("📋 Annotations")
        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        header_layout.addWidget(title_label)

        # Overall status
        picks_count = len(self._loaded_data.get("picks", []))
        meshes_count = len(self._loaded_data.get("meshes", []))
        seg_count = len(self._loaded_data.get("segmentations", []))
        total_count = picks_count + meshes_count + seg_count

        all_loaded = all(status == "loaded" for status in [picks_status, meshes_status, seg_status])
        any_loading = any(status == "loading" for status in [picks_status, meshes_status, seg_status])

        if any_loading:
            status_label = self._create_status_label("loading", "")
            status_label.setText("Loading annotations...")
        elif all_loaded:
            status_label = self._create_status_label("loaded", "")
            status_label.setText(f"✓ {total_count} annotations")
        else:
            status_label = self._create_status_label("pending", "")
            status_label.setText("Pending...")

        status_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        header_layout.addStretch()
        header_layout.addWidget(status_label)

        section_layout.addLayout(header_layout)

        # Subsections
        subsections_widget = QWidget()
        subsections_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        subsections_layout = QVBoxLayout()
        subsections_layout.setContentsMargins(10, 0, 0, 0)
        subsections_layout.setSpacing(8)

        # Add each annotation type
        subsections_layout.addWidget(self._create_annotation_subsection("picks", "📍 Picks", picks_status))
        subsections_layout.addWidget(self._create_annotation_subsection("meshes", "🕸 Meshes", meshes_status))
        subsections_layout.addWidget(self._create_annotation_subsection("segmentations", "🖌 Segmentations", seg_status))

        subsections_widget.setLayout(subsections_layout)
        section_layout.addWidget(subsections_widget)

        section_frame.setLayout(section_layout)
        self._content_layout.addWidget(section_frame)

    def _create_section_frame(self) -> QFrame:
        """Create a styled frame for a section."""
        frame = QFrame(objectName="section_frame")
        frame.setFrameStyle(QFrame.StyledPanel)
        colors = self.theme_interface.get_theme_colors()
        frame.setStyleSheet(
            f"""
            QFrame[objectName="section_frame"] {{
                background-color: {colors['bg_secondary']};
                border-radius: 8px;
                border: 1px solid {colors['border_primary']};
            }}
        """,
        )
        return frame

    def _create_status_label(self, status: str, data_type: str) -> QLabel:
        """Create a status indicator label with theme-aware styling."""
        label = QLabel()
        label.setAlignment(Qt.AlignCenter)
        colors = self.theme_interface.get_theme_colors()

        if status == "loading":
            label.setText("Loading...")
            label.setStyleSheet(
                f"""
                QLabel {{
                    background-color: {colors['warning']};
                    color: white;
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-size: 10px;
                    font-weight: bold;
                }}
            """,
            )
        elif status == "loaded":
            count = len(self._loaded_data.get(data_type, []))
            label.setText(f"✓ Loaded ({count} items)")
            label.setStyleSheet(
                f"""
                QLabel {{
                    background-color: {colors['success']};
                    color: white;
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-size: 10px;
                    font-weight: bold;
                }}
            """,
            )
        elif status.startswith("error:"):
            error_msg = status[6:]
            label.setText(f"✗ Error: {error_msg[:20]}...")
            label.setStyleSheet(
                f"""
                QLabel {{
                    background-color: {colors['error']};
                    color: white;
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-size: 10px;
                    font-weight: bold;
                }}
            """,
            )
        else:
            label.setText("Pending...")
            label.setStyleSheet(
                f"""
                QLabel {{
                    background-color: {colors['text_muted']};
                    color: white;
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-size: 10px;
                    font-weight: bold;
                }}
            """,
            )

        return label

    def _create_content_placeholder(self, status: str) -> QLabel:
        """Create a placeholder label for content."""
        if status == "loading":
            text = "Loading data..."
        elif status.startswith("error:"):
            text = "Failed to load data"
        else:
            text = "Not loaded yet"

        label = QLabel(text)
        label.setAlignment(Qt.AlignCenter)
        colors = self.theme_interface.get_theme_colors()
        label.setStyleSheet(f"color: {colors['text_muted']}; font-style: italic; padding: 20px;")
        return label

    def _create_nested_voxel_tomogram_content(
        self,
        voxel_spacings: List["CopickVoxelSpacing"],
        tomograms: List["CopickTomogram"],
    ) -> QWidget:
        """Create nested voxel spacing and tomogram content."""
        content_widget = QWidget()
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)

        # Group tomograms by voxel spacing
        voxel_to_tomos = {}
        for vs in voxel_spacings:
            voxel_to_tomos[vs.voxel_size] = []

        for tomo in tomograms:
            vs_size = tomo.voxel_spacing.voxel_size
            if vs_size in voxel_to_tomos:
                voxel_to_tomos[vs_size].append(tomo)

        for vs in voxel_spacings:
            vs_widget = self._create_voxel_spacing_widget(vs, voxel_to_tomos.get(vs.voxel_size, []))
            content_layout.addWidget(vs_widget)

        content_widget.setLayout(content_layout)
        return content_widget

    def _create_voxel_spacing_widget(
        self,
        voxel_spacing: "CopickVoxelSpacing",
        tomograms: List["CopickTomogram"],
    ) -> QFrame:
        """Create a widget for a voxel spacing with its tomograms."""
        frame = QFrame(objectName="vs_frame")
        frame.setFrameStyle(QFrame.StyledPanel)
        colors = self.theme_interface.get_theme_colors()
        frame.setStyleSheet(
            f"""
            QFrame[objectName="vs_frame"] {{
                background-color: {colors['bg_primary']};
                border-radius: 6px;
                border: 1px solid {colors['border_primary']};
            }}
        """,
        )

        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Header with voxel spacing info
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)

        header_label = QLabel(f"📏 Voxel Spacing {voxel_spacing.voxel_size:.2f}Å")
        header_font = QFont()
        header_font.setPointSize(12)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_layout.addWidget(header_label)

        # Add CryoET link if applicable
        link_button = self._create_portal_link_button(voxel_spacing)
        if link_button:
            header_layout.addStretch()
            header_layout.addWidget(link_button)

        layout.addLayout(header_layout)

        # Tomograms grid
        if tomograms:
            # Create a grid layout for tomogram cards
            tomo_grid_widget = QWidget()
            tomo_grid_layout = QGridLayout()
            tomo_grid_layout.setContentsMargins(15, 0, 0, 0)
            tomo_grid_layout.setSpacing(8)

            # Calculate grid dimensions (3 columns)
            cols = 3

            for i, tomo in enumerate(tomograms):
                row = i // cols
                col = i % cols

                tomo_card = self._create_tomogram_card(tomo)
                tomo_grid_layout.addWidget(tomo_card, row, col)

            tomo_grid_widget.setLayout(tomo_grid_layout)
            layout.addWidget(tomo_grid_widget)
        else:
            empty_label = QLabel("No tomograms found")
            colors = self.theme_interface.get_theme_colors()
            empty_label.setStyleSheet(f"color: {colors['text_muted']}; font-style: italic; margin-left: 15px;")
            layout.addWidget(empty_label)

        frame.setLayout(layout)
        return frame

    def _create_tomogram_card(self, tomogram: "CopickTomogram") -> QFrame:
        """Create a card widget for a tomogram with thumbnail."""
        card = QFrame(objectName="info_card")
        card.setFrameStyle(QFrame.StyledPanel)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        card.setMinimumSize(200, 240)
        colors = self.theme_interface.get_theme_colors()
        card.setStyleSheet(
            f"""
            QFrame[objectName="info_card"] {{
                background-color: {colors['bg_tertiary']};
                border-radius: 8px;
                border: 1px solid {colors['border_secondary']};
            }}
            QFrame[objectName="info_card"]:hover {{
                border: 1px solid {colors['border_accent']};
                background-color: {colors['bg_quaternary']};
            }}
        """,
        )

        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Thumbnail area
        thumbnail_label = QLabel()
        thumbnail_label.setObjectName("thumbnail_label")
        thumbnail_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        thumbnail_label.setAlignment(Qt.AlignCenter)
        thumbnail_label.setScaledContents(False)
        colors = self.theme_interface.get_theme_colors()
        thumbnail_label.setStyleSheet(
            f"""
            QLabel {{
                background-color: {colors['bg_secondary']};
                border-radius: 6px;
                border: 1px solid {colors['border_primary']};
            }}
        """,
        )

        # Create unique ID for this tomogram thumbnail
        thumbnail_id = f"tomo_{id(tomogram)}"

        # Check if thumbnail is already loaded
        if thumbnail_id in self._thumbnails:
            # Use cached thumbnail
            pixmap = self._thumbnails[thumbnail_id]
            max_size = min(card.minimumSize().width() - 40, card.minimumSize().height() - 80)
            scaled_pixmap = self.image_interface.scale_pixmap(pixmap, (max_size, max_size), smooth=False)
            thumbnail_label.setPixmap(scaled_pixmap)
        else:
            # Show loading placeholder and start async loading
            thumbnail_label.setText("⏳")
            thumbnail_label.setStyleSheet(
                thumbnail_label.styleSheet()
                + f"""
                QLabel {{
                    color: {colors['text_muted']};
                    font-size: 24px;
                }}
            """,
            )

            # Store widget reference for later update
            self._thumbnail_widgets[thumbnail_id] = card

            # Start async thumbnail loading
            if not self._is_destroyed:
                self._load_tomogram_thumbnail(tomogram, thumbnail_id)

        layout.addWidget(thumbnail_label)

        # Info section
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)

        # Tomogram name
        name_label = QLabel(tomogram.tomo_type)
        name_label.setAlignment(Qt.AlignCenter)
        colors = self.theme_interface.get_theme_colors()
        name_label.setStyleSheet(f"color: {colors['text_primary']}; font-weight: bold; font-size: 10px;")
        name_label.setWordWrap(True)
        info_layout.addWidget(name_label)

        # CryoET link if applicable
        link_button = self._create_portal_link_button(tomogram)
        if link_button:
            link_button.setFixedHeight(18)
            link_button.setStyleSheet(link_button.styleSheet() + "font-size: 8px; padding: 1px 4px;")
            info_layout.addWidget(link_button)

        info_widget = QWidget()
        info_widget.setLayout(info_layout)
        layout.addWidget(info_widget)

        # Make the card clickable
        card.mousePressEvent = lambda event: self._on_tomogram_card_clicked(tomogram)

        card.setLayout(layout)
        return card

    def _load_tomogram_thumbnail(self, tomogram: "CopickTomogram", thumbnail_id: str) -> None:
        """Start async loading of tomogram thumbnail."""
        if self._is_destroyed:
            return

        # Use the shared worker interface to load thumbnails directly from tomogram
        self.worker_interface.start_thumbnail_worker(
            item=tomogram,  # Pass the specific tomogram instead of the run
            thumbnail_id=thumbnail_id,
            callback=self._on_thumbnail_loaded,
            force_regenerate=False,
        )

    def _on_thumbnail_loaded(self, thumbnail_id: str, pixmap: Optional[Any], error: Optional[str]) -> None:
        """Handle thumbnail loading completion."""
        if self._is_destroyed or thumbnail_id not in self._thumbnail_widgets:
            return

        if error:
            # Could show error placeholder
            pass
        else:
            # Store the thumbnail
            self._thumbnails[thumbnail_id] = pixmap

            # Update the widget if it exists
            if thumbnail_id in self._thumbnail_widgets:
                widget = self._thumbnail_widgets[thumbnail_id]
                try:
                    if widget and not widget.isHidden():
                        # Find the thumbnail label and update it
                        thumbnail_label = widget.findChild(QLabel, "thumbnail_label")
                        if thumbnail_label and not thumbnail_label.isHidden():
                            widget_size = thumbnail_label.size()
                            max_size = min(widget_size.width() - 20, widget_size.height() - 20)
                            if max_size > 0:
                                scaled_pixmap = self.image_interface.scale_pixmap(
                                    pixmap,
                                    (max_size, max_size),
                                    smooth=False,
                                )
                                thumbnail_label.setPixmap(scaled_pixmap)
                    else:
                        del self._thumbnail_widgets[thumbnail_id]
                except RuntimeError:
                    if thumbnail_id in self._thumbnail_widgets:
                        del self._thumbnail_widgets[thumbnail_id]

    def _create_annotation_subsection(self, data_type: str, title: str, status: str) -> QFrame:
        """Create an annotation subsection widget."""
        frame = QFrame(objectName="annotation_section")
        frame.setFrameStyle(QFrame.StyledPanel)
        colors = self.theme_interface.get_theme_colors()
        frame.setStyleSheet(
            f"""
            QFrame[objectName="annotation_section"] {{
                background-color: {colors['bg_primary']};
                border-radius: 4px;
                border: 1px solid {colors['border_primary']};
            }}
        """,
        )

        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Subsection header
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)

        title_label = QLabel(title)
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)

        # Status indicator
        if status == "loading":
            status_label = QLabel("⏳")
        elif status == "loaded":
            count = len(self._loaded_data.get(data_type, []))
            status_label = QLabel(f"({count})")
        elif status.startswith("error:"):
            status_label = QLabel("⚠️")
        else:
            status_label = QLabel("⏳")

        colors = self.theme_interface.get_theme_colors()
        status_label.setStyleSheet(f"color: {colors['text_muted']}; font-size: 10px;")
        header_layout.addStretch()
        header_layout.addWidget(status_label)

        layout.addLayout(header_layout)

        # Content
        if status == "loaded" and data_type in self._loaded_data:
            data = self._loaded_data[data_type]
            if data:
                content_widget = self._create_annotation_items_widget(data_type, data)
                layout.addWidget(content_widget)
            else:
                empty_label = QLabel("No items found")
                colors = self.theme_interface.get_theme_colors()
                empty_label.setStyleSheet(f"color: {colors['text_muted']}; font-style: italic; margin-left: 10px;")
                layout.addWidget(empty_label)
        else:
            content_label = self._create_content_placeholder(status)
            layout.addWidget(content_label)

        frame.setLayout(layout)
        return frame

    def _create_annotation_items_widget(self, data_type: str, data: List[Any]) -> QWidget:
        """Create a widget containing annotation items."""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 0, 0, 0)
        layout.setSpacing(4)

        # Show all items
        for item in data:
            item_widget = self._create_annotation_item_widget(data_type, item)
            layout.addWidget(item_widget)

        widget.setLayout(layout)
        return widget

    def _create_annotation_item_widget(self, data_type: str, item: Any) -> QWidget:
        """Create a widget for a single annotation item."""
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        # Info layout
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)

        if data_type == "picks":
            name = f"📍 {item.pickable_object_name}"
            point_count = len(item.points) if hasattr(item, "points") else "N/A"
            details = f"User: {item.user_id} | Session: {item.session_id} | Points: {point_count}"
        elif data_type == "meshes":
            name = f"🕸 {item.pickable_object_name}"
            details = f"User: {item.user_id} | Session: {item.session_id}"
        elif data_type == "segmentations":
            seg_name = getattr(
                item,
                "name",
                item.pickable_object_name if hasattr(item, "pickable_object_name") else "Unknown",
            )
            name = f"🖌 {seg_name}"
            details = f"User: {item.user_id} | Session: {item.session_id}"
        else:
            name = str(item)
            details = ""

        # Name label
        name_label = QLabel(name)
        colors = self.theme_interface.get_theme_colors()
        name_label.setStyleSheet(f"color: {colors['text_primary']}; font-weight: bold; font-size: 11px;")
        info_layout.addWidget(name_label)

        # Details label
        if details:
            details_label = QLabel(details)
            colors = self.theme_interface.get_theme_colors()
            details_label.setStyleSheet(f"color: {colors['text_muted']}; font-size: 9px;")
            info_layout.addWidget(details_label)

        layout.addLayout(info_layout)
        layout.addStretch()

        # Add CryoET link if applicable
        link_button = self._create_portal_link_button(item)
        if link_button:
            layout.addWidget(link_button)

        widget.setLayout(layout)

        # Apply theme-aware styling
        colors = self.theme_interface.get_theme_colors()
        widget.setStyleSheet(
            f"""
            QWidget {{
                background-color: {colors['bg_tertiary']};
                border-radius: 4px;
            }}
        """,
        )
        return widget

    def _create_portal_link_button(self, item: Any) -> Optional[QPushButton]:
        """Create a CryoET Data Portal link button for an item if applicable."""
        portal_url = self.session_interface.get_portal_link(item)
        if portal_url:
            button = QPushButton("🌐 Portal")
            button.setStyleSheet(self.theme_interface.get_button_stylesheet("primary"))
            button.clicked.connect(lambda: self._open_url(portal_url))
            return button
        return None

    def _open_url(self, url: str) -> None:
        """Open URL in default browser."""
        from qtpy.QtCore import QUrl
        from qtpy.QtGui import QDesktopServices

        QDesktopServices.openUrl(QUrl(url))

    @Slot()
    def _on_back_to_gallery(self) -> None:
        """Handle back to gallery button click."""
        self.session_interface.navigate_to_gallery()

    def _on_tomogram_card_clicked(self, tomogram: "CopickTomogram") -> None:
        """Handle click on tomogram card."""
        # Emit signal for external handling
        self.tomogram_clicked.emit(tomogram)

        # Also use session interface to load tomogram
        self.session_interface.load_tomogram_and_switch_view(tomogram)
