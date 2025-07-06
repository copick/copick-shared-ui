"""Platform-specific theme detection."""

from typing import Optional, Callable

try:
    from qtpy.QtWidgets import QApplication
    from qtpy.QtCore import QObject
    from qtpy.QtGui import QPalette
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False


def detect_theme() -> str:
    """Detect current theme (light/dark)."""
    try:
        # Try napari theme detection first
        theme = _detect_napari_theme()
        if theme:
            return theme
            
        # Fall back to Qt theme detection
        theme = _detect_qt_theme()
        if theme:
            return theme
            
    except Exception:
        pass
        
    # Default to light theme
    return "light"


def _detect_napari_theme() -> Optional[str]:
    """Detect napari theme."""
    try:
        import napari
        
        # Try to get the current napari theme
        if hasattr(napari, 'current_theme'):
            theme_name = napari.current_theme()
            if 'dark' in theme_name.lower():
                return "dark"
            elif 'light' in theme_name.lower():
                return "light"
                
        # Try to get theme from napari settings
        if hasattr(napari, 'settings') and hasattr(napari.settings, 'appearance'):
            theme_name = napari.settings.appearance.theme
            if 'dark' in theme_name.lower():
                return "dark"
            elif 'light' in theme_name.lower():
                return "light"
                
    except Exception:
        pass
        
    return None


def _detect_qt_theme() -> Optional[str]:
    """Detect Qt theme based on palette."""
    if not QT_AVAILABLE:
        return None
        
    try:
        app = QApplication.instance()
        if not app:
            return None
            
        palette = app.palette()
        
        # Check if window background is dark
        window_color = palette.color(QPalette.Window)
        brightness = (window_color.red() + window_color.green() + window_color.blue()) / 3
        
        # If average brightness is less than 128, consider it dark theme
        return "dark" if brightness < 128 else "light"
        
    except Exception:
        return None


def connect_theme_change_qt(callback: Callable[[], None]) -> bool:
    """Connect to Qt theme change events."""
    if not QT_AVAILABLE:
        return False
        
    try:
        app = QApplication.instance()
        if app and hasattr(app, 'paletteChanged'):
            app.paletteChanged.connect(callback)
            return True
    except Exception:
        pass
        
    return False


def connect_theme_change_napari(callback: Callable[[], None]) -> bool:
    """Connect to napari theme change events."""
    try:
        import napari
        
        # Try to connect to napari's theme change event
        if hasattr(napari, 'settings') and hasattr(napari.settings, 'appearance'):
            napari.settings.appearance.events.theme.connect(callback)
            return True
            
    except Exception:
        pass
        
    return False


def connect_theme_change(callback: Callable[[], None]) -> bool:
    """Connect to theme change events (tries both napari and Qt)."""
    napari_connected = connect_theme_change_napari(callback)
    qt_connected = connect_theme_change_qt(callback)
    
    return napari_connected or qt_connected