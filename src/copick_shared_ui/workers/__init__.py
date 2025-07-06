"""Worker implementations for background processing."""

from .base import AbstractThumbnailWorker

try:
    from .chimerax import ChimeraXThumbnailWorker, ChimeraXWorkerManager, ChimeraXWorkerSignals

    CHIMERAX_AVAILABLE = True
except ImportError:
    CHIMERAX_AVAILABLE = False

try:
    from .napari import NapariThumbnailWorker, NapariWorkerManager, NapariWorkerSignals

    NAPARI_AVAILABLE = True
except ImportError:
    NAPARI_AVAILABLE = False

__all__ = [
    "AbstractThumbnailWorker",
]

if CHIMERAX_AVAILABLE:
    __all__.extend(
        [
            "ChimeraXThumbnailWorker",
            "ChimeraXWorkerManager",
            "ChimeraXWorkerSignals",
        ],
    )

if NAPARI_AVAILABLE:
    __all__.extend(
        [
            "NapariThumbnailWorker",
            "NapariWorkerManager",
            "NapariWorkerSignals",
        ],
    )
