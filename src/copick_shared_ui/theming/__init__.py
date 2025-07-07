"""Theming support for gallery widgets."""

from copick_shared_ui.theming.colors import get_color_schemes
from copick_shared_ui.theming.styles import generate_button_stylesheet, generate_input_stylesheet, generate_stylesheet
from copick_shared_ui.theming.theme_detection import detect_theme

__all__ = [
    "get_color_schemes",
    "generate_stylesheet",
    "generate_button_stylesheet",
    "generate_input_stylesheet",
    "detect_theme",
]
