"""Abstract interfaces for platform-agnostic gallery functionality."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

if TYPE_CHECKING:
    from copick.models import CopickRun, CopickTomogram


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


class AbstractWorkerInterface(ABC):
    """Abstract interface for background worker management."""

    @abstractmethod
    def start_thumbnail_worker(
        self,
        run: "CopickRun",
        thumbnail_id: str,
        callback: Callable[[str, Optional[Any], Optional[str]], None],
        force_regenerate: bool = False,
    ) -> None:
        """Start a thumbnail loading worker."""
        pass

    @abstractmethod
    def clear_workers(self) -> None:
        """Clear all pending workers."""
        pass

    @abstractmethod
    def shutdown_workers(self, timeout_ms: int = 3000) -> None:
        """Shutdown all workers with timeout."""
        pass


class AbstractImageInterface(ABC):
    """Abstract interface for image/pixmap handling."""

    @abstractmethod
    def create_pixmap_from_array(self, array: Any) -> Any:
        """Create a platform-specific pixmap from numpy array."""
        pass

    @abstractmethod
    def scale_pixmap(self, pixmap: Any, size: tuple, smooth: bool = True) -> Any:
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
