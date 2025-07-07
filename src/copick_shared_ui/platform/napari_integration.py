"""napari-specific integration for gallery widget."""

from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Union

try:
    from qtpy.QtCore import Qt
    from qtpy.QtGui import QPixmap

    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False

from copick_shared_ui.core.models import (
    AbstractImageInterface,
    AbstractSessionInterface,
    AbstractThemeInterface,
    AbstractWorkerInterface,
)
from copick_shared_ui.theming.colors import get_color_scheme
from copick_shared_ui.theming.styles import (
    generate_button_stylesheet,
    generate_input_stylesheet,
    generate_stylesheet,
)
from copick_shared_ui.workers.napari import NapariWorkerManager

if TYPE_CHECKING:
    import napari
    from copick.models import CopickRun, CopickTomogram


class NapariSessionInterface(AbstractSessionInterface):
    """napari-specific session interface."""

    def __init__(self, viewer: "napari.Viewer"):
        self.viewer = viewer
        self._copick_root = None

    def get_copick_root(self) -> Optional[Any]:
        """Get the current copick root object."""
        return self._copick_root

    def set_copick_root(self, copick_root: Any) -> None:
        """Set the copick root object."""
        self._copick_root = copick_root

    def switch_to_3d_view(self) -> None:
        """Switch to 3D/volume view."""
        # napari is always in 3D view mode
        pass

    def load_tomogram(self, tomogram: "CopickTomogram") -> None:
        """Load a tomogram into the napari viewer.

        Note: This method is deprecated in favor of the async loading mechanism
        in the napari plugin. It's kept for compatibility but should not be used
        for new implementations.
        """
        print("Warning: load_tomogram is deprecated. Use async loading in napari plugin instead.")

    def expand_run_in_tree(self, run: "CopickRun") -> None:
        """Expand the run in the tree view."""
        # napari doesn't have a tree view like ChimeraX
        # This could be implemented if there's a tree widget in the plugin
        pass


class NapariThemeInterface(AbstractThemeInterface):
    """napari-specific theme interface."""

    def __init__(self, viewer: "napari.Viewer"):
        self.viewer = viewer
        self._current_theme = self._detect_napari_theme()

    def _detect_napari_theme(self) -> str:
        """Detect theme from napari viewer."""
        try:
            napari_theme = str(self.viewer.theme)

            # Map napari themes to our theme system
            if napari_theme.lower() == "light":
                return "light"
            elif napari_theme.lower() == "dark":
                return "dark"
            else:
                # For custom themes or unknown themes, default to dark
                return "dark"

        except Exception as e:
            print(f"🎨 Error detecting napari theme: {e}, defaulting to dark")
            return "dark"

    def get_theme_colors(self) -> Dict[str, str]:
        """Get color scheme for current theme."""
        # Refresh theme in case it changed
        self._current_theme = self._detect_napari_theme()
        return get_color_scheme(self._current_theme)

    def get_theme_stylesheet(self) -> str:
        """Get base stylesheet for current theme."""
        # Refresh theme in case it changed
        self._current_theme = self._detect_napari_theme()
        return generate_stylesheet(self._current_theme)

    def get_button_stylesheet(self, button_type: str = "primary") -> str:
        """Get button stylesheet for current theme."""
        # Refresh theme in case it changed
        self._current_theme = self._detect_napari_theme()
        return generate_button_stylesheet(button_type, self._current_theme)

    def get_input_stylesheet(self) -> str:
        """Get input field stylesheet for current theme."""
        # Refresh theme in case it changed
        self._current_theme = self._detect_napari_theme()
        return generate_input_stylesheet(self._current_theme)

    def connect_theme_changed(self, callback: Callable[[], None]) -> None:
        """Connect to theme change events."""
        try:
            # Connect to napari's theme change events
            self.viewer.events.theme.connect(lambda event: callback())
        except Exception as e:
            print(f"⚠️ Could not connect to napari theme events: {e}")
            # Fallback: periodically check theme changes
            pass


class NapariWorkerInterface(AbstractWorkerInterface):
    """napari-specific worker interface."""

    def __init__(self):
        self._manager = NapariWorkerManager()

    def start_thumbnail_worker(
        self,
        item: Union["CopickRun", "CopickTomogram"],
        thumbnail_id: str,
        callback: Callable[[str, Optional[Any], Optional[str]], None],
        force_regenerate: bool = False,
    ) -> None:
        """Start a thumbnail loading worker."""
        self._manager.start_thumbnail_worker(item, thumbnail_id, callback, force_regenerate)

    def start_data_worker(
        self,
        run: "CopickRun",
        data_type: str,
        callback: Callable[[str, Optional[Any], Optional[str]], None],
    ) -> None:
        """Start a data loading worker for the specified data type."""
        self._manager.start_data_worker(run, data_type, callback)

    def clear_workers(self) -> None:
        """Clear all pending workers."""
        self._manager.clear_workers()

    def shutdown_workers(self, timeout_ms: int = 3000) -> None:
        """Shutdown all workers with timeout."""
        self._manager.shutdown_workers(timeout_ms)


class NapariImageInterface(AbstractImageInterface):
    """napari-specific image interface."""

    def create_pixmap_from_array(self, array: Any) -> Any:
        """Create a QPixmap from numpy array."""
        if not QT_AVAILABLE:
            return None

        try:
            from qtpy.QtGui import QImage

            if array.ndim == 2:
                # Grayscale image
                height, width = array.shape
                bytes_per_line = width

                # Create QImage from array
                qimage = QImage(array.data, width, height, bytes_per_line, QImage.Format_Grayscale8)

                # Convert to QPixmap
                pixmap = QPixmap.fromImage(qimage)
                return pixmap

            elif array.ndim == 3 and array.shape[2] == 3:
                # RGB image
                height, width, channels = array.shape
                bytes_per_line = width * channels

                # Create QImage from array
                qimage = QImage(array.data, width, height, bytes_per_line, QImage.Format_RGB888)

                # Convert to QPixmap
                pixmap = QPixmap.fromImage(qimage)
                return pixmap

            return None

        except Exception as e:
            print(f"Error creating pixmap from array: {e}")
            return None

    def scale_pixmap(self, pixmap: Any, size: tuple, smooth: bool = False) -> Any:
        """Scale a QPixmap to the specified size."""
        if not QT_AVAILABLE or not pixmap:
            return pixmap

        try:
            from qtpy.QtCore import QSize

            # Handle both tuple and QSize inputs
            if isinstance(size, QSize):  # noqa: SIM108
                # Already a QSize object
                qt_size = size
            else:
                # Tuple or list - convert to QSize
                qt_size = QSize(size[0], size[1])

            aspect_ratio = Qt.KeepAspectRatio
            transform = Qt.SmoothTransformation if smooth else Qt.FastTransformation

            return pixmap.scaled(qt_size, aspect_ratio, transform)

        except Exception as e:
            print(f"Error scaling pixmap: {e}")
            return pixmap

    def save_pixmap(self, pixmap: Any, path: str) -> bool:
        """Save QPixmap to file."""
        if not QT_AVAILABLE or not pixmap:
            return False

        try:
            return pixmap.save(path)
        except Exception as e:
            print(f"Error saving pixmap: {e}")
            return False

    def load_pixmap(self, path: str) -> Optional[Any]:
        """Load QPixmap from file."""
        if not QT_AVAILABLE:
            return None

        try:
            pixmap = QPixmap(path)
            return pixmap if not pixmap.isNull() else None
        except Exception as e:
            print(f"Error loading pixmap: {e}")
            return None


class NapariGalleryIntegration:
    """Complete napari integration for gallery widget."""

    def __init__(self, viewer: "napari.Viewer"):
        self.viewer = viewer
        self.session_interface = NapariSessionInterface(viewer)
        self.theme_interface = NapariThemeInterface(viewer)
        self.worker_interface = NapariWorkerInterface()
        self.image_interface = NapariImageInterface()

    def create_gallery_widget(self, parent=None):
        """Create a gallery widget with napari integration."""
        from copick_shared_ui.widgets.gallery.gallery_widget import CopickGalleryWidget

        return CopickGalleryWidget(
            self.session_interface,
            self.theme_interface,
            self.worker_interface,
            self.image_interface,
            parent,
        )

    def set_copick_root(self, copick_root: Any) -> None:
        """Set the copick root for the session."""
        self.session_interface.set_copick_root(copick_root)
