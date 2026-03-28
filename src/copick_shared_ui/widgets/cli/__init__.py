"""CLI tool widgets for auto-generating Qt UI from Click command definitions."""

from copick_shared_ui.widgets.cli.command_browser import ClickCommandBrowser
from copick_shared_ui.widgets.cli.command_form import ClickCommandForm

__all__ = [
    "ClickCommandBrowser",
    "ClickCommandForm",
]
