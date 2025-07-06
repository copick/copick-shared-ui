"""Concrete implementations of ImageInterface for different GUI frameworks.

Uses qtpy for Qt compatibility across different Qt backends.
"""

from typing import Any, Optional

from .thumbnail_cache import ImageInterface


class QtImageInterface(ImageInterface):
    """Qt-based image interface for ChimeraX and other Qt applications."""

    def __init__(self):
        """Initialize the Qt image interface."""
        try:
            from qtpy.QtGui import QPixmap

            self._QPixmap = QPixmap
        except ImportError as err:
            raise ImportError(
                "No Qt GUI library found. Please install a Qt library (PyQt5, PyQt6, PySide2, or PySide6) and qtpy.",
            ) from err

    def save_image(self, image: Any, path: str, format: str = "PNG") -> bool:
        """Save a QPixmap to disk.

        Args:
            image: QPixmap object
            path: File path to save to
            format: Image format (default: PNG)

        Returns:
            True if successful, False otherwise
        """
        try:
            if not isinstance(image, self._QPixmap):
                return False
            return image.save(path, format)
        except Exception:
            return False

    def load_image(self, path: str) -> Optional[Any]:
        """Load a QPixmap from disk.

        Args:
            path: File path to load from

        Returns:
            QPixmap if successful, None otherwise
        """
        try:
            pixmap = self._QPixmap(path)
            return pixmap if not pixmap.isNull() else None
        except Exception:
            return None

    def is_valid_image(self, image: Any) -> bool:
        """Check if a QPixmap is valid.

        Args:
            image: QPixmap to check

        Returns:
            True if valid, False otherwise
        """
        try:
            return isinstance(image, self._QPixmap) and not image.isNull()
        except Exception:
            return False


class NumpyImageInterface(ImageInterface):
    """Numpy-based image interface for napari and other applications."""

    def __init__(self):
        """Initialize the numpy image interface."""
        try:
            import numpy as np
            from PIL import Image

            self._np = np
            self._Image = Image
        except ImportError as err:
            raise ImportError(
                "NumPy and Pillow are required for NumpyImageInterface. "
                "Please install them with: pip install numpy pillow",
            ) from err

    def save_image(self, image: Any, path: str, format: str = "PNG") -> bool:
        """Save a numpy array as an image.

        Args:
            image: numpy array (H, W, C) or (H, W) with dtype uint8
            path: File path to save to
            format: Image format (default: PNG)

        Returns:
            True if successful, False otherwise
        """
        try:
            if not isinstance(image, self._np.ndarray):
                return False

            # Convert to PIL Image
            if len(image.shape) == 2:
                # Grayscale image
                pil_image = self._Image.fromarray(image, mode="L")
            elif len(image.shape) == 3:
                if image.shape[2] == 3:
                    # RGB image
                    pil_image = self._Image.fromarray(image, mode="RGB")
                elif image.shape[2] == 4:
                    # RGBA image
                    pil_image = self._Image.fromarray(image, mode="RGBA")
                else:
                    return False
            else:
                return False

            # Save the image
            pil_image.save(path, format)
            return True
        except Exception:
            return False

    def load_image(self, path: str) -> Optional[Any]:
        """Load an image as a numpy array.

        Args:
            path: File path to load from

        Returns:
            numpy array if successful, None otherwise
        """
        try:
            pil_image = self._Image.open(path)
            return self._np.array(pil_image)
        except Exception:
            return None

    def is_valid_image(self, image: Any) -> bool:
        """Check if a numpy array is a valid image.

        Args:
            image: numpy array to check

        Returns:
            True if valid, False otherwise
        """
        try:
            if not isinstance(image, self._np.ndarray):
                return False

            # Check if it's a valid image shape
            if len(image.shape) == 2:
                # Grayscale
                return True
            elif len(image.shape) == 3 and image.shape[2] in [3, 4]:  # noqa: SIM103
                # RGB or RGBA
                return True
            else:
                return False
        except Exception:
            return False


def create_image_interface(framework: str = "auto") -> ImageInterface:
    """Create an appropriate image interface based on the framework.

    Args:
        framework: Framework name ('qt', 'numpy', 'auto')

    Returns:
        ImageInterface instance

    Raises:
        ValueError: If framework is not supported
        ImportError: If required dependencies are not available
    """
    if framework == "auto":
        # Try to detect the framework
        try:
            # Check for Qt via qtpy (recommended approach)
            import qtpy  # noqa: F401

            return QtImageInterface()
        except ImportError:
            try:
                # Check for Qt directly (ChimeraX compatibility)
                import Qt  # noqa: F401

                return QtImageInterface()
            except ImportError:
                # Fall back to numpy
                return NumpyImageInterface()

    elif framework == "qt":
        return QtImageInterface()

    elif framework == "numpy":
        return NumpyImageInterface()

    else:
        raise ValueError(f"Unsupported framework: {framework}")
