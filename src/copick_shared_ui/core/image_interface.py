"""Platform-agnostic image interfaces for thumbnail caching."""

from typing import Any, Optional

from .thumbnail_cache import ImageInterface


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
            print(f"🖼️ Qt interface initialized with qtpy: {QPixmap}")
        except ImportError:
            print(f"🖼️ qtpy not available, trying Qt fallback")
            try:
                # Fall back to Qt (ChimeraX)
                from Qt.QtGui import QPixmap

                self._QPixmap = QPixmap
                self._qt_available = True
                print(f"🖼️ Qt interface initialized with Qt: {QPixmap}")
            except ImportError:
                print(f"❌ No Qt interface available")
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
        print(f"🖼️ Qt save_image called: {path}")
        print(f"🖼️ Qt available: {self._qt_available}")
        print(f"🖼️ Image provided: {image is not None}")
        
        if not self._qt_available:
            print(f"❌ Qt not available for save operation")
            return False
            
        if not image:
            print(f"❌ No image provided for save operation")
            return False

        try:
            print(f"🖼️ Image type: {type(image)}")
            print(f"🖼️ Image isNull: {image.isNull() if hasattr(image, 'isNull') else 'No isNull method'}")
            print(f"🖼️ Image size: {image.size() if hasattr(image, 'size') else 'No size method'}")
            
            # QPixmap has a save method
            result = image.save(path, format)
            print(f"🖼️ Qt save result: {result}")
            
            # Verify the file was actually written
            from pathlib import Path
            saved_path = Path(path)
            if saved_path.exists():
                print(f"🖼️ File successfully written: {saved_path.stat().st_size} bytes")
            else:
                print(f"❌ File not found after save operation: {path}")
                
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
        print(f"🖼️ Qt load_image called: {path}")
        print(f"🖼️ Qt available: {self._qt_available}")
        
        if not self._qt_available:
            print(f"❌ Qt not available for load operation")
            return None

        try:
            from pathlib import Path
            path_obj = Path(path)
            print(f"🖼️ File exists: {path_obj.exists()}")
            if path_obj.exists():
                print(f"🖼️ File size: {path_obj.stat().st_size} bytes")
            
            pixmap = self._QPixmap(path)
            print(f"🖼️ QPixmap created: {pixmap is not None}")
            
            if pixmap:
                is_null = pixmap.isNull()
                print(f"🖼️ QPixmap isNull: {is_null}")
                if not is_null:
                    print(f"🖼️ QPixmap size: {pixmap.size()}")
                    print(f"🖼️ QPixmap format: {pixmap.format() if hasattr(pixmap, 'format') else 'No format method'}")
                return pixmap if not is_null else None
            else:
                print(f"🖼️ QPixmap creation returned None")
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
        print(f"🖼️ Qt is_valid_image called")
        print(f"🖼️ Qt available: {self._qt_available}")
        print(f"🖼️ Image provided: {image is not None}")
        
        if not self._qt_available:
            print(f"❌ Qt not available for validation")
            return False
            
        if not image:
            print(f"❌ No image provided for validation")
            return False

        try:
            # QPixmap has isNull method
            is_null = image.isNull()
            is_valid = not is_null
            print(f"🖼️ Image isNull: {is_null}, isValid: {is_valid}")
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
