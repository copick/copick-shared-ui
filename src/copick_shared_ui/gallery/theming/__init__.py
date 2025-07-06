"""Theming support for gallery widgets."""

from .colors import get_color_schemes
from .styles import generate_stylesheet, generate_button_stylesheet, generate_input_stylesheet
from .theme_detection import detect_theme

__all__ = [
    "get_color_schemes",
    "generate_stylesheet", 
    "generate_button_stylesheet",
    "generate_input_stylesheet",
    "detect_theme",
]