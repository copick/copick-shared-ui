"""OpenMoji font loader for copick-ui ecosystem.

Loads the OpenMoji font from openmoji-dist package and provides
functions to apply OpenMoji for emoji rendering.

IMPORTANT: Use stylesheets (not setFont) for reliable emoji rendering.
Qt stylesheets override setFont(), so always use the stylesheet approach.

Usage:
    from copick_shared_ui.icons import OPENMOJI_FONT_CSS

    # Apply to any widget with emoji text via stylesheet
    label = QLabel("📍 Picks")
    label.setStyleSheet(f"{OPENMOJI_FONT_CSS} font-size: 12pt;")

    # Or combine with other styles
    button.setStyleSheet(f"color: white; {OPENMOJI_FONT_CSS}")
"""

import logging
from pathlib import Path
from typing import Optional

from qtpy.QtGui import QFont, QFontDatabase

logger = logging.getLogger(__name__)

# Global font state
_openmoji_font_id: Optional[int] = None
_openmoji_font_family: Optional[str] = None
_initialization_attempted: bool = False


def initialize_openmoji_font() -> bool:
    """Load OpenMoji font from openmoji-dist package.

    Called automatically on first use of get_openmoji_font().
    Returns True if successful, False otherwise.
    """
    global _openmoji_font_id, _openmoji_font_family, _initialization_attempted

    # Only attempt initialization once
    if _initialization_attempted:
        return _openmoji_font_family is not None

    _initialization_attempted = True

    font_path = None

    # Method 1: Find package location WITHOUT importing (avoids importlib.resources issues)
    try:
        import importlib.util

        spec = importlib.util.find_spec("openmoji_dist")
        if spec and spec.origin:
            pkg_path = Path(spec.origin).parent
            # Try COLRv1 first (newer, better support), fall back to COLRv0
            font_path = pkg_path / "openmoji" / "font" / "glyf_colr0.ttf"
            if not font_path.exists():
                font_path = pkg_path / "openmoji" / "font" / "glyf_colr0.ttf"
            logger.debug(f"Found openmoji-dist via find_spec: {font_path}")
    except Exception as e:
        logger.debug(f"find_spec method failed: {e}")

    # Method 2: Search sys.path directly (no import needed)
    if font_path is None or not font_path.exists():
        try:
            import sys

            for search_path in sys.path:
                if not search_path:
                    continue
                # Try COLRv1 first, fall back to COLRv0
                for font_name in ["glyf_colr0.ttf", "glyf_colr1.ttf"]:
                    candidate = Path(search_path) / "openmoji_dist" / "openmoji" / "font" / font_name
                    if candidate.exists():
                        font_path = candidate
                        logger.debug(f"Found openmoji-dist via sys.path: {font_path}")
                        break
                if font_path and font_path.exists():
                    break
        except Exception as e:
            logger.debug(f"sys.path search failed: {e}")

    if font_path is None or not font_path.exists():
        logger.warning(f"OpenMoji font not found (searched path: {font_path})")
        return False

    # Load the font into Qt
    try:
        _openmoji_font_id = QFontDatabase.addApplicationFont(str(font_path))

        if _openmoji_font_id < 0:
            logger.warning("Failed to load OpenMoji font into Qt")
            return False

        families = QFontDatabase.applicationFontFamilies(_openmoji_font_id)
        if families:
            _openmoji_font_family = families[0]
            logger.info(f"OpenMoji font loaded: {_openmoji_font_family}")
            return True

        logger.warning("OpenMoji font loaded but no families found")
        return False

    except Exception as e:
        logger.warning(f"Error loading OpenMoji font into Qt: {e}")
        return False


def get_openmoji_font(point_size: int = 12) -> QFont:
    """Get a QFont configured with OpenMoji.

    Args:
        point_size: Font size in points

    Returns:
        QFont with OpenMoji family, or default font if unavailable

    Example:
        label = QLabel("📍 Picks")
        label.setFont(get_openmoji_font(12))
    """
    if _openmoji_font_family is None:
        initialize_openmoji_font()

    if _openmoji_font_family:
        font = QFont(_openmoji_font_family)
    else:
        font = QFont()

    font.setPointSize(point_size)
    return font


def get_openmoji_stylesheet(point_size: int = 12) -> str:
    """Get a CSS stylesheet string for OpenMoji font.

    Alternative to setFont() - sometimes stylesheets work better for emoji fonts.

    Args:
        point_size: Font size in points

    Returns:
        CSS font-family string, or empty string if unavailable

    Example:
        label = QLabel("📍 Picks")
        label.setStyleSheet(get_openmoji_stylesheet(12))
    """
    if _openmoji_font_family is None:
        initialize_openmoji_font()

    if _openmoji_font_family:
        return f"font-family: '{_openmoji_font_family}'; font-size: {point_size}pt;"
    return ""


def get_openmoji_family() -> Optional[str]:
    """Get the OpenMoji font family name.

    Returns:
        Font family name if loaded, None otherwise
    """
    if _openmoji_font_family is None:
        initialize_openmoji_font()
    return _openmoji_font_family


def get_openmoji_font_css() -> str:
    """Get font-family CSS with OpenMoji for emojis and system fonts for text.

    Returns a font stack where OpenMoji is used for emoji characters and
    system fonts are used for regular text.

    Returns:
        CSS font-family declaration with fallbacks, or empty string if unavailable

    Example:
        label.setStyleSheet(f"{get_openmoji_font_css()} font-size: 12pt; color: white;")
    """
    if _openmoji_font_family is None:
        initialize_openmoji_font()

    if _openmoji_font_family:
        # Font stack: System fonts first for text, OpenMoji as fallback for emojis
        # System fonts don't have emoji glyphs, so Qt falls back to OpenMoji for emojis
        return f"font-family: 'Segoe UI', 'SF Pro', 'Helvetica Neue', sans-serif, '{_openmoji_font_family}';"
    return ""


# Convenience constant - initialized lazily on first access
class _OpenMojiFontCSS:
    """Lazy-loading font CSS constant."""

    def __init__(self) -> None:
        self._css: Optional[str] = None

    def __str__(self) -> str:
        if self._css is None:
            self._css = get_openmoji_font_css()
        return self._css

    def __repr__(self) -> str:
        return str(self)

    def __add__(self, other: str) -> str:
        return str(self) + other

    def __radd__(self, other: str) -> str:
        return other + str(self)


OPENMOJI_FONT_CSS = _OpenMojiFontCSS()
