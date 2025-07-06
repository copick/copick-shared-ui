"""Color schemes for gallery theming."""

from typing import Dict

# Color schemes for different themes
COLOR_SCHEMES = {
    "light": {
        "bg_primary": "#ffffff",
        "bg_secondary": "#f5f5f5", 
        "bg_tertiary": "#e8e8e8",
        "bg_quaternary": "#d1d1d1",
        "text_primary": "#2c2c2c",
        "text_secondary": "#4a4a4a",
        "text_muted": "#888888",
        "border_primary": "#cccccc",
        "border_secondary": "#e0e0e0",
        "border_accent": "#4682b4",
        "accent_primary": "#4682b4",
        "accent_secondary": "#5a9bd4",
        "success": "#28a745",
        "warning": "#ffc107",
        "error": "#dc3545",
    },
    "dark": {
        "bg_primary": "#2d2d2d",
        "bg_secondary": "#3a3a3a",
        "bg_tertiary": "#404040",
        "bg_quaternary": "#4a4a4a",
        "text_primary": "#ffffff",
        "text_secondary": "#e0e0e0",
        "text_muted": "#a0a0a0",
        "border_primary": "#555555",
        "border_secondary": "#666666",
        "border_accent": "#70a8d8",
        "accent_primary": "#70a8d8",
        "accent_secondary": "#85b3db",
        "success": "#28a745",
        "warning": "#ffc107",
        "error": "#dc3545",
    }
}


def get_color_schemes() -> Dict[str, Dict[str, str]]:
    """Get all available color schemes."""
    return COLOR_SCHEMES


def get_color_scheme(theme: str) -> Dict[str, str]:
    """Get colors for a specific theme."""
    return COLOR_SCHEMES.get(theme, COLOR_SCHEMES["light"])


def interpolate_colors(color1: str, color2: str, factor: float) -> str:
    """Interpolate between two hex colors."""
    try:
        # Remove # prefix if present
        color1 = color1.lstrip('#')
        color2 = color2.lstrip('#')
        
        # Convert to RGB
        r1, g1, b1 = int(color1[0:2], 16), int(color1[2:4], 16), int(color1[4:6], 16)
        r2, g2, b2 = int(color2[0:2], 16), int(color2[2:4], 16), int(color2[4:6], 16)
        
        # Interpolate
        r = int(r1 + (r2 - r1) * factor)
        g = int(g1 + (g2 - g1) * factor)
        b = int(b1 + (b2 - b1) * factor)
        
        # Convert back to hex
        return f"#{r:02x}{g:02x}{b:02x}"
        
    except Exception:
        return color1  # Fallback to first color