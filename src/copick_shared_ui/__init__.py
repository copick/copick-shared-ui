"""Copick shared UI components for cross-platform visualization."""

__version__ = "0.1.1"

# Core components
from .core import (
    AbstractImageInterface,
    AbstractInfoSessionInterface,
    AbstractSessionInterface,
    AbstractThemeInterface,
    AbstractWorkerInterface,
    ThumbnailCache,
    get_global_cache,
    set_global_cache_config,
)

# UI components
from .ui.edit_object_types_dialog import ColorButton, EditObjectTypesDialog

# Utilities
from .util.validation import generate_smart_copy_name, get_invalid_characters, validate_copick_name

__all__ = [
    # Core interfaces and caching
    "AbstractImageInterface",
    "AbstractInfoSessionInterface",
    "AbstractSessionInterface",
    "AbstractThemeInterface",
    "AbstractWorkerInterface",
    "ThumbnailCache",
    "get_global_cache",
    "set_global_cache_config",
    # UI components
    "EditObjectTypesDialog",
    "ColorButton",
    # Utilities
    "validate_copick_name",
    "get_invalid_characters",
    "generate_smart_copy_name",
]
