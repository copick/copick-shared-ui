"""ChimeraX-specific integration for gallery widget."""

from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

try:
    from qtpy.QtCore import Qt
    from qtpy.QtGui import QPixmap

    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False

from ..gallery.core.models import (
    AbstractImageInterface,
    AbstractSessionInterface,
    AbstractThemeInterface,
    AbstractWorkerInterface,
)
from ..gallery.theming import (
    detect_theme,
    generate_button_stylesheet,
    generate_input_stylesheet,
    generate_stylesheet,
)
from ..gallery.theming.colors import get_color_scheme
from ..gallery.workers.chimerax_workers import ChimeraXWorkerManager

if TYPE_CHECKING:
    from chimerax.core.session import Session
    from copick.models import CopickRun, CopickTomogram


class ChimeraXSessionInterface(AbstractSessionInterface):
    """ChimeraX-specific session interface."""

    def __init__(self, session: "Session"):
        self.session = session

    def get_copick_root(self) -> Optional[Any]:
        """Get the current copick root object."""
        return getattr(self.session, "copick_root", None)

    def set_copick_root(self, copick_root: Any) -> None:
        """Set the copick root object."""
        self.session.copick_root = copick_root

    def switch_to_3d_view(self) -> None:
        """Switch to 3D/volume view."""
        try:
            # Get the main window and stack widget for view switching
            main_window = self.session.ui.main_window
            stack_widget = main_window._stack

            # Switch to OpenGL view (index 0)
            stack_widget.setCurrentIndex(0)

        except Exception as e:
            print(f"Error switching to 3D view: {e}")

    def load_tomogram(self, tomogram: "CopickTomogram") -> None:
        """Load a tomogram into the ChimeraX viewer."""
        try:
            copick_tool = self.session.copick

            # Find the tomogram in the tree and get its QModelIndex
            tomogram_index = self._find_tomogram_in_tree(tomogram)

            if tomogram_index and tomogram_index.isValid():
                # Use the copick tool's switch_volume method
                copick_tool.switch_volume(tomogram_index)

            # Expand the run in the tree widget
            self.expand_run_in_tree(tomogram.voxel_spacing.run)

        except Exception as e:
            print(f"Error loading tomogram: {e}")

    def expand_run_in_tree(self, run: "CopickRun") -> None:
        """Expand the run in the tree view."""
        try:
            copick_tool = self.session.copick
            tree_view = copick_tool._mw._tree_view
            model = tree_view.model()

            if not model:
                return

            # Find the run in the tree model and expand it
            for row in range(model.rowCount()):
                index = model.index(row, 0)
                if index.isValid():
                    # Get the item and check if it matches our run
                    from qtpy.QtCore import QSortFilterProxyModel

                    if isinstance(model, QSortFilterProxyModel):
                        source_index = model.mapToSource(index)
                        item = source_index.internalPointer()
                    else:
                        item = index.internalPointer()

                    # Check if this is the right run
                    if hasattr(item, "run") and item.run == run or hasattr(item, "name") and item.name == run.name:
                        tree_view.expand(index)
                        tree_view.setCurrentIndex(index)

                        # Also expand all voxel spacings within this run
                        self._expand_all_voxel_spacings(model, index)
                        break

        except Exception as e:
            print(f"Error expanding run in tree: {e}")

    def _find_tomogram_in_tree(self, tomogram: "CopickTomogram") -> Optional[Any]:
        """Find the tomogram in the tree model and return its QModelIndex."""
        try:
            copick_tool = self.session.copick
            tree_view = copick_tool._mw._tree_view
            model = tree_view.model()

            if not model:
                return None

            from qtpy.QtCore import QSortFilterProxyModel

            # Get current run from tomogram
            current_run = tomogram.voxel_spacing.run

            # Navigate the tree structure: Root -> Run -> VoxelSpacing -> Tomogram
            for run_row in range(model.rowCount()):
                run_index = model.index(run_row, 0)
                if not run_index.isValid():
                    continue

                # Get the actual item (handling proxy model if present)
                if isinstance(model, QSortFilterProxyModel):
                    source_run_index = model.mapToSource(run_index)
                    run_item = source_run_index.internalPointer()
                else:
                    run_item = run_index.internalPointer()

                if not run_item:
                    continue

                # Check if this is the right run
                if hasattr(run_item, "run"):
                    if run_item.run.name != current_run.name:
                        continue
                elif hasattr(run_item, "name"):
                    if run_item.name != current_run.name:
                        continue
                else:
                    continue

                # Search through voxel spacings and tomograms
                for vs_row in range(model.rowCount(run_index)):
                    vs_index = model.index(vs_row, 0, run_index)
                    if not vs_index.isValid():
                        continue

                    # Get voxel spacing item
                    if isinstance(model, QSortFilterProxyModel):
                        source_vs_index = model.mapToSource(vs_index)
                        vs_item = source_vs_index.internalPointer()
                    else:
                        vs_item = vs_index.internalPointer()

                    if not vs_item:
                        continue

                    # Check if this voxel spacing contains our tomogram
                    if hasattr(vs_item, "voxel_spacing"):
                        vs_obj = vs_item.voxel_spacing
                        if vs_obj.voxel_size != tomogram.voxel_spacing.voxel_size:
                            continue
                    else:
                        continue

                    # Search through tomograms
                    for tomo_row in range(model.rowCount(vs_index)):
                        tomo_index = model.index(tomo_row, 0, vs_index)
                        if not tomo_index.isValid():
                            continue

                        # Get tomogram item
                        if isinstance(model, QSortFilterProxyModel):
                            source_tomo_index = model.mapToSource(tomo_index)
                            tomo_item = source_tomo_index.internalPointer()
                            final_index = source_tomo_index
                        else:
                            tomo_item = tomo_index.internalPointer()
                            final_index = tomo_index

                        if not tomo_item:
                            continue

                        # Check if this is our tomogram
                        if hasattr(tomo_item, "tomogram"):
                            tomo_obj = tomo_item.tomogram
                            if (
                                tomo_obj.tomo_type == tomogram.tomo_type
                                and tomo_obj.voxel_spacing.voxel_size == tomogram.voxel_spacing.voxel_size
                            ):
                                return final_index

            return None

        except Exception as e:
            print(f"Error finding tomogram in tree: {e}")
            return None

    def _expand_all_voxel_spacings(self, model: Any, run_index: Any) -> None:
        """Expand all voxel spacings under the given run."""
        try:
            copick_tool = self.session.copick
            tree_view = copick_tool._mw._tree_view

            from qtpy.QtCore import QSortFilterProxyModel

            # Force lazy loading of voxel spacings
            if isinstance(model, QSortFilterProxyModel):
                source_run_index = model.mapToSource(run_index)
                run_item = source_run_index.internalPointer()
            else:
                run_item = run_index.internalPointer()

            if hasattr(run_item, "children"):
                vs_children = run_item.children  # Force lazy loading
                vs_count = len(vs_children)
            else:
                vs_count = model.rowCount(run_index)

            # Expand each voxel spacing
            for vs_row in range(vs_count):
                vs_index = model.index(vs_row, 0, run_index)
                if vs_index.isValid():
                    tree_view.expand(vs_index)

        except Exception as e:
            print(f"Error expanding voxel spacings: {e}")


class ChimeraXThemeInterface(AbstractThemeInterface):
    """ChimeraX-specific theme interface."""

    def __init__(self):
        self._current_theme = detect_theme()

    def get_theme_colors(self) -> Dict[str, str]:
        """Get color scheme for current theme."""
        return get_color_scheme(self._current_theme)

    def get_theme_stylesheet(self) -> str:
        """Get base stylesheet for current theme."""
        return generate_stylesheet(self._current_theme)

    def get_button_stylesheet(self, button_type: str = "primary") -> str:
        """Get button stylesheet for current theme."""
        return generate_button_stylesheet(button_type, self._current_theme)

    def get_input_stylesheet(self) -> str:
        """Get input field stylesheet for current theme."""
        return generate_input_stylesheet(self._current_theme)

    def connect_theme_changed(self, callback: Callable[[], None]) -> None:
        """Connect to theme change events."""
        # Note: ChimeraX theme change events would need to be implemented
        # This would connect to ChimeraX's theme system if available
        pass


class ChimeraXWorkerInterface(AbstractWorkerInterface):
    """ChimeraX-specific worker interface."""

    def __init__(self):
        self._manager = ChimeraXWorkerManager()

    def start_thumbnail_worker(
        self,
        run: "CopickRun",
        thumbnail_id: str,
        callback: Callable[[str, Optional[Any], Optional[str]], None],
        force_regenerate: bool = False,
    ) -> None:
        """Start a thumbnail loading worker."""
        self._manager.start_thumbnail_worker(run, thumbnail_id, callback, force_regenerate)

    def clear_workers(self) -> None:
        """Clear all pending workers."""
        self._manager.clear_workers()

    def shutdown_workers(self, timeout_ms: int = 3000) -> None:
        """Shutdown all workers with timeout."""
        self._manager.shutdown_workers(timeout_ms)


class ChimeraXImageInterface(AbstractImageInterface):
    """ChimeraX-specific image interface."""

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

    def scale_pixmap(self, pixmap: Any, size: tuple, smooth: bool = True) -> Any:
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


class ChimeraXGalleryIntegration:
    """Complete ChimeraX integration for gallery widget."""

    def __init__(self, session: "Session"):
        self.session = session
        self.session_interface = ChimeraXSessionInterface(session)
        self.theme_interface = ChimeraXThemeInterface()
        self.worker_interface = ChimeraXWorkerInterface()
        self.image_interface = ChimeraXImageInterface()

    def create_gallery_widget(self, parent=None):
        """Create a gallery widget with ChimeraX integration."""
        from ..gallery.core.gallery_widget import CopickGalleryWidget

        return CopickGalleryWidget(
            self.session_interface,
            self.theme_interface,
            self.worker_interface,
            self.image_interface,
            parent,
        )
