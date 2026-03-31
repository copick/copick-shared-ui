"""Core abstract interfaces for platform-agnostic copick shared UI components."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Union

if TYPE_CHECKING:
    from copick.models import CopickRun, CopickTomogram


# Session management interfaces
class AbstractSessionInterface(ABC):
    """Abstract interface for session management across platforms."""

    @abstractmethod
    def get_copick_root(self) -> Optional[Any]:
        """Get the current copick root object."""
        pass

    @abstractmethod
    def switch_to_3d_view(self) -> None:
        """Switch to 3D/volume view."""
        pass

    @abstractmethod
    def load_tomogram(self, tomogram: "CopickTomogram") -> None:
        """Load a tomogram into the viewer."""
        pass

    @abstractmethod
    def expand_run_in_tree(self, run: "CopickRun") -> None:
        """Expand the run in the tree view."""
        pass


class AbstractInfoSessionInterface(ABC):
    """Abstract interface for session management in info widget."""

    @abstractmethod
    def load_tomogram_and_switch_view(self, tomogram: "CopickTomogram") -> None:
        """Load the tomogram and switch to volume view."""
        pass

    @abstractmethod
    def navigate_to_gallery(self) -> None:
        """Navigate back to gallery view."""
        pass

    @abstractmethod
    def expand_run_in_tree(self, run: "CopickRun") -> None:
        """Expand the run in the tree view."""
        pass

    def get_portal_link(self, item) -> Optional[str]:
        """Get CryoET Data Portal link for an item if applicable."""
        try:
            # Import here to avoid circular imports
            from copick.impl.cryoet_data_portal import CopickRunCDP

            # Check if this is a CryoET Data Portal project
            if hasattr(item, "run") and isinstance(item.run, CopickRunCDP):
                run_id = item.run.portal_run_id

                if hasattr(item, "meta") and hasattr(item.meta, "portal_tomo_id"):
                    # Tomogram link
                    return f"https://cryoetdataportal.czscience.com/runs/{run_id}?table-tab=Tomograms"
                elif hasattr(item, "meta") and hasattr(item.meta, "portal_annotation_id"):
                    # Annotation link (picks, segmentations)
                    return f"https://cryoetdataportal.czscience.com/runs/{run_id}?table-tab=Annotations"
                elif (
                    hasattr(item, "voxel_spacing")
                    and hasattr(item.voxel_spacing, "run")
                    and isinstance(item.voxel_spacing.run, CopickRunCDP)
                ):
                    # Voxel spacing or tomogram via voxel spacing
                    run_id = item.voxel_spacing.run.portal_run_id
                    return f"https://cryoetdataportal.czscience.com/runs/{run_id}"
                else:
                    # General run link
                    return f"https://cryoetdataportal.czscience.com/runs/{run_id}"

            return None
        except Exception:
            return None


# Theme and styling interfaces
class AbstractThemeInterface(ABC):
    """Abstract interface for theme detection and styling."""

    @abstractmethod
    def get_theme_colors(self) -> Dict[str, str]:
        """Get color scheme for current theme."""
        pass

    @abstractmethod
    def get_theme_stylesheet(self) -> str:
        """Get base stylesheet for current theme."""
        pass

    @abstractmethod
    def get_button_stylesheet(self, button_type: str = "primary") -> str:
        """Get button stylesheet for current theme."""
        pass

    @abstractmethod
    def get_input_stylesheet(self) -> str:
        """Get input field stylesheet for current theme."""
        pass

    @abstractmethod
    def connect_theme_changed(self, callback: Callable[[], None]) -> None:
        """Connect to theme change events."""
        pass


# Worker interfaces
class AbstractWorkerInterface(ABC):
    """Abstract interface for background worker management."""

    @abstractmethod
    def start_thumbnail_worker(
        self,
        item: Union["CopickRun", "CopickTomogram"],
        thumbnail_id: str,
        callback: Callable[[str, Optional[Any], Optional[str]], None],
        force_regenerate: bool = False,
    ) -> None:
        """Start a thumbnail loading worker for either a run or specific tomogram."""
        pass

    @abstractmethod
    def start_data_worker(
        self,
        run: "CopickRun",
        data_type: str,
        callback: Callable[[str, Optional[Any], Optional[str]], None],
    ) -> None:
        """Start a data loading worker for the specified data type."""
        pass

    @abstractmethod
    def clear_workers(self) -> None:
        """Clear all pending workers."""
        pass

    @abstractmethod
    def shutdown_workers(self, timeout_ms: int = 3000) -> None:
        """Shutdown all workers with timeout."""
        pass


# Image/pixmap interfaces
class AbstractImageInterface(ABC):
    """Abstract interface for image/pixmap handling."""

    def create_pixmap_from_array(self, array: Any) -> Any:
        """Create a platform-specific pixmap from numpy array."""
        try:
            import numpy as np

            # Try to import Qt modules - prefer qtpy for napari compatibility
            try:
                from qtpy.QtGui import QImage, QPixmap
            except ImportError:
                try:
                    from Qt.QtGui import QImage, QPixmap
                except ImportError:
                    return None

            if array.ndim == 2:
                # Grayscale image
                height, width = array.shape
                bytes_per_line = width

                # Ensure array is uint8
                if array.dtype != np.uint8:
                    # Normalize to 0-255 range
                    array_min, array_max = array.min(), array.max()
                    if array_max > array_min:
                        array = ((array - array_min) / (array_max - array_min) * 255).astype(np.uint8)
                    else:
                        array = np.zeros_like(array, dtype=np.uint8)

                # Create QImage from array
                qimage = QImage(array.data, width, height, bytes_per_line, QImage.Format_Grayscale8)

                # Convert to QPixmap
                return QPixmap.fromImage(qimage)

            elif array.ndim == 3 and array.shape[2] == 3:
                # RGB image
                height, width, channels = array.shape
                bytes_per_line = width * channels

                # Ensure array is uint8
                if array.dtype != np.uint8:
                    array = (array * 255).astype(np.uint8)

                # Create QImage from array
                qimage = QImage(array.data, width, height, bytes_per_line, QImage.Format_RGB888)

                # Convert to QPixmap
                return QPixmap.fromImage(qimage)

            else:
                print(f"Unsupported array shape: {array.shape}")
                return None

        except Exception as e:
            print(f"Error converting array to pixmap: {e}")
            return None

    @abstractmethod
    def scale_pixmap(self, pixmap: Any, size: tuple, smooth: bool = False) -> Any:
        """Scale a pixmap to the specified size."""
        pass

    @abstractmethod
    def save_pixmap(self, pixmap: Any, path: str) -> bool:
        """Save pixmap to file."""
        pass

    @abstractmethod
    def load_pixmap(self, path: str) -> Optional[Any]:
        """Load pixmap from file."""
        pass


# CLI tool interfaces
class AbstractCLIContextInterface(ABC):
    """Abstract interface for providing CLI context (auto-fill, project state).

    Platform implementations read from the active copick project to provide
    context-aware data for auto-filling CLI command parameters.
    """

    @abstractmethod
    def get_config_path(self) -> Optional[str]:
        """Get the current copick config file path (for --config auto-fill).

        If the project was loaded from dataset IDs (no file), the implementation
        should serialize the config to a temp file and return that path.
        """
        pass

    @abstractmethod
    def get_copick_root(self) -> Optional[Any]:
        """Get the current copick root object."""
        pass

    @abstractmethod
    def get_run_names(self) -> List[str]:
        """Get list of available run names for run selector auto-fill."""
        pass

    @abstractmethod
    def get_object_names(self) -> List[str]:
        """Get list of available pickable object names."""
        pass

    @abstractmethod
    def get_voxel_spacings(self) -> List[float]:
        """Get list of available voxel spacings."""
        pass

    @abstractmethod
    def get_user_ids(self) -> List[str]:
        """Get list of known user IDs from the project."""
        pass

    @abstractmethod
    def get_session_ids(self) -> List[str]:
        """Get list of known session IDs from the project."""
        pass

    @abstractmethod
    def get_tomo_types(self) -> List[str]:
        """Get list of available tomogram types."""
        pass

    def get_selected_copick_object(self) -> Optional[Any]:
        """Get the currently selected copick object from the tree/viewer.

        Returns the copick model object (CopickPicks, CopickSegmentation,
        CopickTomogram, etc.) for the currently selected UI element, or None.
        Default returns None; platforms with a tree view should override.
        """
        return None

    def connect_selection_changed(self, callback: Callable[[Any], None]) -> None:
        """Connect to tree/viewer selection changes.

        The callback receives the selected copick object when selection changes.
        Default is a no-op; platforms with a tree view should override.
        """
        pass

    def disconnect_selection_changed(self, callback: Callable[[Any], None]) -> None:
        """Disconnect a previously connected selection callback.

        Default is a no-op; platforms with a tree view should override.
        """
        pass


class AbstractCLIRefreshInterface(ABC):
    """Abstract interface for refreshing views after CLI command execution.

    Platform implementations trigger appropriate view updates based on
    the type of command that was executed.
    """

    @abstractmethod
    def refresh_after_command(self, command_category: str) -> None:
        """Refresh views after a CLI command completes.

        Args:
            command_category: The category of the command that ran
                (e.g. "Data Management", "Data Processing", "Utilities").
        """
        pass
