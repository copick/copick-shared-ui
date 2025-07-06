"""Abstract base classes for background data loading workers."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Callable, List, Optional

if TYPE_CHECKING:
    from copick.models import CopickRun


class AbstractDataWorker(ABC):
    """Abstract base class for data loading workers."""

    def __init__(
        self,
        run: "CopickRun",
        data_type: str,
        callback: Callable[[str, Optional[List[Any]], Optional[str]], None],
    ):
        self.run = run
        self.data_type = data_type
        self.callback = callback
        self._cancelled = False

    @abstractmethod
    def start(self) -> None:
        """Start the data loading work."""
        pass

    @abstractmethod
    def cancel(self) -> None:
        """Cancel the data loading work."""
        pass

    def load_data(self) -> tuple[Optional[List[Any]], Optional[str]]:
        """Load data for the specified data type. Returns (data, error)."""
        if self._cancelled:
            return None, "Cancelled"

        try:
            if self.data_type == "voxel_spacings":
                data = list(self.run.voxel_spacings)
            elif self.data_type == "tomograms":
                tomograms = []
                for vs in self.run.voxel_spacings:
                    if self._cancelled:
                        return None, "Cancelled"
                    tomograms.extend(list(vs.tomograms))
                data = tomograms
            elif self.data_type == "picks":
                data = list(self.run.picks)
            elif self.data_type == "meshes":
                data = list(self.run.meshes)
            elif self.data_type == "segmentations":
                data = list(self.run.segmentations)
            else:
                return None, f"Unknown data type: {self.data_type}"

            if self._cancelled:
                return None, "Cancelled"

            return data, None

        except Exception as e:
            print(f"❌ Error loading {self.data_type} for run '{self.run.name}': {e}")
            return None, str(e)
