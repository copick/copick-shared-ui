"""Platform-agnostic image interfaces for thumbnail caching."""

from typing import Any, Optional

from copick_shared_ui.core.thumbnail_cache import ImageInterface


class QtImageInterface(ImageInterface):
    """Qt-based image interface for thumbnail caching (works with both qtpy and Qt)."""

    def __init__(self):
        """Initialize the Qt image interface."""
        self._qt_available = False
        self._QPixmap = None
        self._setup_qt()

    def _setup_qt(self) -> None:
        """Set up Qt imports - try qtpy first, then Qt."""
        try:
            # Try qtpy first (napari compatibility)
            from qtpy.QtGui import QPixmap

            self._QPixmap = QPixmap
            self._qt_available = True
        except ImportError:
            try:
                # Fall back to Qt (ChimeraX)
                from Qt.QtGui import QPixmap

                self._QPixmap = QPixmap
                self._qt_available = True
            except ImportError:
                print("❌ No Qt interface available")
                self._qt_available = False

    def save_image(self, image: Any, path: str, format: str = "PNG") -> bool:
        """Save a QPixmap to disk.

        Args:
            image: QPixmap object
            path: File path to save to
            format: Image format (default: PNG)

        Returns:
            True if successful, False otherwise
        """
        if not self._qt_available:
            print("❌ Qt not available for save operation")
            return False

        if not image:
            print("❌ No image provided for save operation")
            return False

        try:
            # QPixmap has a save method
            result = image.save(path, format)

            return result
        except Exception as e:
            print(f"❌ Error saving image: {e}")
            import traceback

            print(f"❌ Stack trace: {traceback.format_exc()}")
            return False

    def load_image(self, path: str) -> Optional[Any]:
        """Load a QPixmap from disk.

        Args:
            path: File path to load from

        Returns:
            QPixmap object if successful, None otherwise
        """
        if not self._qt_available:
            print("❌ Qt not available for load operation")
            return None

        try:
            from pathlib import Path

            pixmap = self._QPixmap(path)

            if pixmap:
                is_null = pixmap.isNull()
                return pixmap if not is_null else None
            else:
                return None
        except Exception as e:
            print(f"❌ Error loading image: {e}")
            import traceback

            print(f"❌ Stack trace: {traceback.format_exc()}")
            return None

    def is_valid_image(self, image: Any) -> bool:
        """Check if a QPixmap is valid.

        Args:
            image: QPixmap object to check

        Returns:
            True if valid, False otherwise
        """
        if not self._qt_available:
            print("❌ Qt not available for validation")
            return False

        if not image:
            print("❌ No image provided for validation")
            return False

        try:
            # QPixmap has isNull method
            is_null = image.isNull()
            is_valid = not is_null
            return is_valid
        except Exception as e:
            print(f"❌ Error validating image: {e}")
            return False


def get_image_interface() -> Optional[ImageInterface]:
    """Get the appropriate image interface for the current environment.

    Returns:
        ImageInterface instance or None if no suitable interface found
    """
    # Try Qt interface first (works for both napari and ChimeraX)
    qt_interface = QtImageInterface()
    if qt_interface._qt_available:
        return qt_interface

    # Could add more interfaces here for other GUI frameworks
    print("❌ No suitable image interface found")
    return None
