"""napari-specific worker implementations using unified thread_worker system."""

from copick_shared_ui.workers.unified_workers import (
    UnifiedDataWorker,
    UnifiedThumbnailWorker,
    UnifiedWorkerManager,
    create_worker_manager,
    get_platform_info,
    is_threading_available,
)

# Re-export unified classes with napari naming for compatibility
NapariThumbnailWorker = UnifiedThumbnailWorker
NapariDataWorker = UnifiedDataWorker
NapariWorkerManager = UnifiedWorkerManager


# Convenience functions
def is_napari_threading_available() -> bool:
    """Check if napari threading is available."""
    return is_threading_available()


def get_napari_platform_info() -> dict:
    """Get napari threading platform information."""
    info = get_platform_info()
    info["platform"] = "napari"
    return info


def create_napari_worker_manager(max_concurrent_workers: int = 8) -> NapariWorkerManager:
    """Create a napari worker manager with platform-appropriate defaults."""
    return create_worker_manager(max_concurrent_workers)
