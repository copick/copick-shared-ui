"""Stylesheet generation for gallery theming."""

from .colors import get_color_scheme


def generate_stylesheet(theme: str) -> str:
    """Generate base stylesheet for theme."""
    colors = get_color_scheme(theme)

    return f"""
        QWidget {{
            background-color: {colors['bg_primary']};
            color: {colors['text_primary']};
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            font-size: 13px;
        }}

        QLabel {{
            background-color: transparent;
            color: {colors['text_primary']};
        }}

        QFrame {{
            background-color: {colors['bg_secondary']};
            border: 1px solid {colors['border_primary']};
            border-radius: 4px;
        }}

        QScrollArea {{
            border: none;
            background-color: {colors['bg_primary']};
        }}

        QScrollArea QScrollBar:vertical {{
            background-color: {colors['bg_secondary']};
            border: none;
            width: 12px;
            border-radius: 6px;
        }}

        QScrollArea QScrollBar::handle:vertical {{
            background-color: {colors['border_primary']};
            border-radius: 6px;
            min-height: 20px;
        }}

        QScrollArea QScrollBar::handle:vertical:hover {{
            background-color: {colors['border_accent']};
        }}

        QScrollArea QScrollBar::add-line:vertical,
        QScrollArea QScrollBar::sub-line:vertical {{
            height: 0px;
            subcontrol-position: bottom;
            subcontrol-origin: margin;
        }}

        QScrollArea QScrollBar:horizontal {{
            background-color: {colors['bg_secondary']};
            border: none;
            height: 12px;
            border-radius: 6px;
        }}

        QScrollArea QScrollBar::handle:horizontal {{
            background-color: {colors['border_primary']};
            border-radius: 6px;
            min-width: 20px;
        }}

        QScrollArea QScrollBar::handle:horizontal:hover {{
            background-color: {colors['border_accent']};
        }}

        QScrollArea QScrollBar::add-line:horizontal,
        QScrollArea QScrollBar::sub-line:horizontal {{
            width: 0px;
            subcontrol-position: right;
            subcontrol-origin: margin;
        }}
    """


def generate_button_stylesheet(button_type: str, theme: str) -> str:
    """Generate button stylesheet for theme."""
    colors = get_color_scheme(theme)

    if button_type == "primary":
        return f"""
            QPushButton {{
                background-color: {colors['accent_primary']};
                color: white;
                border: 1px solid {colors['accent_primary']};
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
                min-width: 80px;
            }}

            QPushButton:hover {{
                background-color: {colors['accent_secondary']};
                border-color: {colors['accent_secondary']};
            }}

            QPushButton:pressed {{
                background-color: {colors['border_accent']};
                border-color: {colors['border_accent']};
            }}

            QPushButton:disabled {{
                background-color: {colors['bg_tertiary']};
                color: {colors['text_muted']};
                border-color: {colors['border_primary']};
            }}
        """
    elif button_type == "secondary":
        return f"""
            QPushButton {{
                background-color: {colors['bg_secondary']};
                color: {colors['text_primary']};
                border: 1px solid {colors['border_primary']};
                border-radius: 4px;
                padding: 8px 16px;
                min-width: 80px;
            }}

            QPushButton:hover {{
                background-color: {colors['bg_tertiary']};
                border-color: {colors['border_accent']};
            }}

            QPushButton:pressed {{
                background-color: {colors['bg_quaternary']};
                border-color: {colors['border_accent']};
            }}

            QPushButton:disabled {{
                background-color: {colors['bg_secondary']};
                color: {colors['text_muted']};
                border-color: {colors['border_primary']};
            }}
        """
    elif button_type == "accent":
        return f"""
            QPushButton {{
                background-color: {colors['accent_primary']};
                color: white;
                border: 1px solid {colors['accent_primary']};
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
                font-size: 12px;
            }}

            QPushButton:hover {{
                background-color: {colors['accent_secondary']};
                border-color: {colors['accent_secondary']};
            }}

            QPushButton:pressed {{
                background-color: {colors['border_accent']};
                border-color: {colors['border_accent']};
            }}

            QPushButton:disabled {{
                background-color: {colors['bg_tertiary']};
                color: {colors['text_muted']};
                border-color: {colors['border_primary']};
            }}
        """
    else:
        return generate_button_stylesheet("primary", theme)


def generate_input_stylesheet(theme: str) -> str:
    """Generate input field stylesheet for theme."""
    colors = get_color_scheme(theme)

    return f"""
        QLineEdit {{
            background-color: {colors['bg_secondary']};
            color: {colors['text_primary']};
            border: 1px solid {colors['border_primary']};
            border-radius: 4px;
            padding: 6px 10px;
            font-size: 13px;
        }}

        QLineEdit:focus {{
            border-color: {colors['border_accent']};
            background-color: {colors['bg_primary']};
        }}

        QLineEdit:disabled {{
            background-color: {colors['bg_tertiary']};
            color: {colors['text_muted']};
            border-color: {colors['border_primary']};
        }}

        QLineEdit::placeholder {{
            color: {colors['text_muted']};
        }}
    """


def generate_status_label_stylesheet(status_type: str, theme: str) -> str:
    """Generate status label stylesheet for theme."""
    colors = get_color_scheme(theme)

    if status_type == "success":
        color = colors["success"]
    elif status_type == "warning":
        color = colors["warning"]
    elif status_type == "error":
        color = colors["error"]
    else:
        color = colors["text_muted"]

    return f"""
        QLabel {{
            color: {color};
            font-size: 11px;
            font-weight: bold;
            padding: 4px 8px;
            border-radius: 3px;
            background-color: transparent;
        }}
    """
