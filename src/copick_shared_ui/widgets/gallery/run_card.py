"""Platform-agnostic run card widget."""

from typing import TYPE_CHECKING, Any, Optional

from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout, QWidget

from copick_shared_ui.core.models import AbstractImageInterface, AbstractThemeInterface

if TYPE_CHECKING:
    from copick.models import CopickRun


class RunCard(QFrame):
    """Individual run card widget with thumbnail and info."""

    clicked = Signal(object)  # Emits the run object
    info_requested = Signal(object)  # Emits the run object for info view

    def __init__(
        self,
        run: "CopickRun",
        theme_interface: AbstractThemeInterface,
        image_interface: AbstractImageInterface,
        parent: Optional[QWidget] = None,
        objectName: str = "run_card",  # noqa: N803
    ) -> None:
        super().__init__(parent)
        self.setObjectName(objectName)
        self.run: "CopickRun" = run
        self.theme_interface = theme_interface
        self.image_interface = image_interface
        self.thumbnail_pixmap: Optional[Any] = None
        self._setup_ui()
        self._setup_style()

    def _setup_ui(self) -> None:
        """Setup the card UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Thumbnail container with info button overlay
        thumbnail_container = QWidget()
        thumbnail_container.setFixedSize(200, 200)

        # Thumbnail label (placeholder)
        self.thumbnail_label = QLabel(thumbnail_container, objectName="run_card_thumbnail_label")
        self.thumbnail_label.setFixedSize(200, 200)
        self.thumbnail_label.setAlignment(Qt.AlignCenter)
        self.thumbnail_label.setText("Loading...")

        # Info button overlay (floating in top-right corner)
        self.info_button = QPushButton("ℹ️", thumbnail_container, objectName="run_card_info_button")
        self.info_button.setFixedSize(24, 24)
        self.info_button.setToolTip("View run details")
        self.info_button.move(170, 6)  # Position in top-right corner with margin
        self.info_button.clicked.connect(lambda: self.info_requested.emit(self.run))

        layout.addWidget(thumbnail_container)

        # Run name label
        self.name_label = QLabel(self.run.name, objectName="run_card_name_label")
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setWordWrap(True)
        layout.addWidget(self.name_label)

        # Status label (for error display)
        self.status_label = QLabel(objectName="run_card_status_label")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setVisible(False)
        layout.addWidget(self.status_label)

    def _setup_style(self) -> None:
        """Setup the card styling."""
        self.setFixedSize(220, 260)
        self.setCursor(Qt.PointingHandCursor)
        self._apply_card_styling()

    def _apply_card_styling(self) -> None:
        """Apply theme-aware styling to this card."""
        colors = self.theme_interface.get_theme_colors()

        # Apply individual component styles
        self.thumbnail_label.setStyleSheet(
            f"""
            QLabel {{
                background-color: {colors['bg_secondary']};
                border: 1px solid {colors['border_primary']};
                border-radius: 4px;
                color: {colors['text_muted']};
            }}
        """,
        )

        self.name_label.setStyleSheet(
            f"""
            QLabel {{
                color: {colors['text_primary']};
                font-weight: bold;
                font-size: 12px;
                padding: 4px;
            }}
        """,
        )

        self.status_label.setStyleSheet(
            """
            QLabel {
                color: #ff6b6b;
                font-size: 10px;
                padding: 2px;
            }
        """,
        )

        self.info_button.setStyleSheet(
            """
            QPushButton {
                background-color: rgba(70, 130, 200, 180);
                border: none;
                border-radius: 12px;
                color: white;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(70, 130, 200, 220);
            }
            QPushButton:pressed {
                background-color: rgba(70, 130, 200, 255);
            }
        """,
        )

    def set_thumbnail(self, pixmap: Optional[Any]) -> None:
        """Set the thumbnail pixmap."""
        if pixmap:
            # Scale pixmap to fit label while maintaining aspect ratio
            scaled_pixmap = self.image_interface.scale_pixmap(pixmap, self.thumbnail_label.size(), smooth=False)
            self.thumbnail_label.setPixmap(scaled_pixmap)
            self.thumbnail_pixmap = pixmap
        else:
            self.thumbnail_label.setText("No thumbnail")

    def set_loading(self, message: str = "Loading...") -> None:
        """Show loading state."""
        try:
            from qtpy.QtGui import QPixmap
        except ImportError:
            from Qt.QtGui import QPixmap
        self.thumbnail_label.setPixmap(QPixmap())  # Clear any existing pixmap
        self.thumbnail_label.setText(message)
        self.status_label.setVisible(False)

    def set_error(self, error_message: str) -> None:
        """Show error state."""
        try:
            from qtpy.QtGui import QPixmap
        except ImportError:
            from Qt.QtGui import QPixmap
        self.thumbnail_label.setPixmap(QPixmap())  # Clear any existing pixmap
        self.thumbnail_label.setText("Error")
        self.status_label.setText(f"Error: {error_message}")
        self.status_label.setVisible(True)

    def mousePressEvent(self, event: Any) -> None:
        """Handle mouse click."""
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.run)
        super().mousePressEvent(event)

    def refresh_theme(self) -> None:
        """Refresh the theme styling."""
        self._apply_card_styling()
