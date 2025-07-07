"""Worker implementations for background processing."""

from copick_shared_ui.workers.base import AbstractThumbnailWorker
from copick_shared_ui.workers.base_manager import AbstractWorkerManager
from copick_shared_ui.workers.data_worker import AbstractDataWorker

# Import unified workers
from copick_shared_ui.workers.unified_workers import (
    UnifiedDataWorker,
    UnifiedThumbnailWorker,
    UnifiedWorkerManager,
    create_worker_manager,
    get_platform_info,
    is_threading_available,
)

# Import platform-specific workers (which now use unified system)
try:
    from copick_shared_ui.workers.chimerax import (
        ChimeraXDataWorker,
        ChimeraXThumbnailWorker,
        ChimeraXWorkerManager,
        create_chimerax_worker_manager,
        get_chimerax_platform_info,
        is_chimerax_threading_available,
    )

    CHIMERAX_AVAILABLE = True
except ImportError:
    CHIMERAX_AVAILABLE = False

try:
    from copick_shared_ui.workers.napari import (
        NapariDataWorker,
        NapariThumbnailWorker,
        NapariWorkerManager,
        create_napari_worker_manager,
        get_napari_platform_info,
        is_napari_threading_available,
    )

    NAPARI_AVAILABLE = True
except ImportError:
    NAPARI_AVAILABLE = False

__all__ = [
    # Base classes
    "AbstractThumbnailWorker",
    "AbstractWorkerManager",
    "AbstractDataWorker",
    # Unified workers
    "UnifiedThumbnailWorker",
    "UnifiedDataWorker",
    "UnifiedWorkerManager",
    "is_threading_available",
    "get_platform_info",
    "create_worker_manager",
]

if CHIMERAX_AVAILABLE:
    __all__.extend(
        [
            "ChimeraXThumbnailWorker",
            "ChimeraXDataWorker",
            "ChimeraXWorkerManager",
            "is_chimerax_threading_available",
            "get_chimerax_platform_info",
            "create_chimerax_worker_manager",
        ],
    )

if NAPARI_AVAILABLE:
    __all__.extend(
        [
            "NapariThumbnailWorker",
            "NapariDataWorker",
            "NapariWorkerManager",
            "is_napari_threading_available",
            "get_napari_platform_info",
            "create_napari_worker_manager",
        ],
    )
