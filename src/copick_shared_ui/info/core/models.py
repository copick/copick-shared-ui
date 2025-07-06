"""Abstract interfaces for platform-agnostic info widget functionality."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from copick.models import CopickRun, CopickTomogram


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

    @abstractmethod
    def get_portal_link(self, item) -> Optional[str]:
        """Get CryoET Data Portal link for an item if applicable."""
        pass
