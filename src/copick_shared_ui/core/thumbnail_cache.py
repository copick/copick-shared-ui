"""Cross-platform thumbnail caching system for copick visualization plugins."""

import hashlib
import json
import os
import platform
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional


class ImageInterface(ABC):
    """Abstract interface for image operations to support different GUI frameworks."""

    @abstractmethod
    def save_image(self, image: Any, path: str, format: str = "PNG") -> bool:
        """Save an image to disk.

        Args:
            image: The image object (framework-specific)
            path: File path to save to
            format: Image format (default: PNG)

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def load_image(self, path: str) -> Optional[Any]:
        """Load an image from disk.

        Args:
            path: File path to load from

        Returns:
            Image object if successful, None otherwise
        """
        pass

    @abstractmethod
    def is_valid_image(self, image: Any) -> bool:
        """Check if an image object is valid.

        Args:
            image: The image object to check

        Returns:
            True if valid, False otherwise
        """
        pass


class ThumbnailCache:
    """Cross-platform thumbnail cache for copick runs and tomograms."""

    def __init__(self, config_path: Optional[str] = None, app_name: str = "copick"):
        """Initialize the thumbnail cache.

        Args:
            config_path: Path to the copick config file (used for cache namespacing)
            app_name: Name of the application (used for cache directory naming)
        """
        self.config_path = config_path
        self.app_name = app_name
        self.config_hash: Optional[str] = None
        self.cache_dir: Optional[Path] = None
        self._image_interface: Optional[ImageInterface] = None
        self._setup_cache_directory()
        # Skip cache cleanup during initialization to avoid blocking main thread
        # self._cleanup_old_cache_entries()

    def set_image_interface(self, image_interface: ImageInterface) -> None:
        """Set the image interface for handling image operations.

        Args:
            image_interface: Implementation of ImageInterface for the specific GUI framework
        """
        self._image_interface = image_interface

    def _setup_cache_directory(self) -> None:
        """Setup the cache directory based on the platform and config."""
        # Get platform-appropriate cache directory
        if platform.system() == "Windows":
            base_cache_dir = Path(os.environ.get("LOCALAPPDATA", "")) / self.app_name / "thumbnails"
        elif platform.system() == "Darwin":  # macOS
            base_cache_dir = Path.home() / "Library" / "Caches" / self.app_name / "thumbnails"
        else:  # Linux and other Unix-like systems
            cache_home = os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))
            base_cache_dir = Path(cache_home) / self.app_name / "thumbnails"

        if self.config_path:
            # Create hash of the config file path and content for cache namespacing
            self.config_hash = self._compute_config_hash(self.config_path)
            self.cache_dir = base_cache_dir / self.config_hash
        else:
            # Fallback to generic cache directory
            self.cache_dir = base_cache_dir / "default"

        # Create the cache directory if it doesn't exist
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

            # Create metadata file FIRST to ensure proper cache initialization
            self._ensure_metadata_file()

        except Exception as e:
            print(f"❌ Error creating cache directory: {e}")
            raise

    def _compute_config_hash(self, config_path: str) -> str:
        """Compute a hash for the config file based on path and content."""
        hasher = hashlib.sha256()

        # Include the config file path
        hasher.update(config_path.encode("utf-8"))

        # Include the config file content if it exists
        try:
            config_file = Path(config_path)
            if config_file.exists():
                with open(config_file, "rb") as f:
                    hasher.update(f.read())
        except Exception:
            # If we can't read the config file, just use the path
            pass

        return hasher.hexdigest()[:16]  # Use first 16 characters for shorter directory names

    def _ensure_metadata_file(self) -> None:
        """Ensure the cache metadata file exists."""
        metadata_file = self.cache_dir / "cache_metadata.json"
        if not metadata_file.exists():
            import time

            metadata = {
                "created_at": str(time.time()),
                "config_path": self.config_path,
                "config_hash": self.config_hash,
                "app_name": self.app_name,
                "version": "1.0",
            }
            with open(metadata_file, "w") as f:
                json.dump(metadata, f, indent=2)

    def get_cache_key(
        self,
        run_name: str,
        tomogram_type: Optional[str] = None,
        voxel_spacing: Optional[float] = None,
    ) -> str:
        """Generate a human-readable cache key for a thumbnail.

        Args:
            run_name: Name of the copick run
            tomogram_type: Type of tomogram (e.g., 'wbp', 'denoised')
            voxel_spacing: Voxel spacing value

        Returns:
            Human-readable cache key string
        """
        key_parts = [run_name]
        if tomogram_type:
            key_parts.append(tomogram_type)
        if voxel_spacing:
            key_parts.append(f"vs{voxel_spacing:.3f}")

        # Use human-readable filename instead of hash
        cache_key = "_".join(key_parts)
        # Replace any problematic characters for filename safety
        cache_key = cache_key.replace("/", "_").replace("\\", "_").replace(":", "_")
        return cache_key

    def get_thumbnail_path(self, cache_key: str) -> Path:
        """Get the file path for a thumbnail cache file.

        Args:
            cache_key: Cache key generated by get_cache_key()

        Returns:
            Path to the thumbnail file
        """
        return self.cache_dir / f"{cache_key}.png"

    def has_thumbnail(self, cache_key: str) -> bool:
        """Check if a thumbnail exists in the cache.

        Args:
            cache_key: Cache key generated by get_cache_key()

        Returns:
            True if thumbnail exists, False otherwise
        """
        thumbnail_path = self.get_thumbnail_path(cache_key)
        exists = thumbnail_path.exists()
        return exists

    def save_thumbnail(self, cache_key: str, image: Any) -> bool:
        """Save a thumbnail to the cache.

        Args:
            cache_key: Cache key generated by get_cache_key()
            image: Image object (framework-specific)

        Returns:
            True if successful, False otherwise
        """
        if not self._image_interface:
            print("❌ Error: No image interface set for thumbnail cache")
            return False

        try:
            thumbnail_path = self.get_thumbnail_path(cache_key)
            success = self._image_interface.save_image(image, str(thumbnail_path), "PNG")
            return success
        except Exception as e:
            print(f"❌ Error saving thumbnail to cache: {e}")
            import traceback

            print(f"❌ Stack trace: {traceback.format_exc()}")
            return False

    def load_thumbnail(self, cache_key: str) -> Optional[Any]:
        """Load a thumbnail from the cache.

        Args:
            cache_key: Cache key generated by get_cache_key()

        Returns:
            Image object if successful, None otherwise
        """
        if not self._image_interface:
            print("❌ Error: No image interface set for thumbnail cache")
            return None

        try:
            thumbnail_path = self.get_thumbnail_path(cache_key)

            if thumbnail_path.exists():
                image = self._image_interface.load_image(str(thumbnail_path))

                if image:
                    is_valid = self._image_interface.is_valid_image(image)
                    return image if is_valid else None
                else:
                    print("🔍 Image load returned None")
                    return None
            else:
                print(f"🔍 Thumbnail file does not exist: {thumbnail_path}")
                return None
        except Exception as e:
            print(f"❌ Error loading thumbnail from cache: {e}")
            import traceback

            print(f"❌ Stack trace: {traceback.format_exc()}")
            return None

    def _cleanup_old_cache_entries(self, max_age_days: int = 14) -> None:
        """Remove cache entries older than the specified number of days.

        Args:
            max_age_days: Maximum age in days for cache entries (default: 14 days)
        """
        if not self.cache_dir or not self.cache_dir.exists():
            return

        try:
            import time

            # current_time = time.time()
            # max_age_seconds = max_age_days * 24 * 60 * 60  # Convert days to seconds
            #
            # removed_count = 0
            # for thumbnail_file in self.cache_dir.glob("*.png"):
            #     try:
            #         # Get file modification time
            #         file_mtime = thumbnail_file.stat().st_mtime
            #         age_seconds = current_time - file_mtime
            #
            #         if age_seconds > max_age_seconds:
            #             thumbnail_file.unlink()
            #             removed_count += 1

            # except Exception as e:
            #     print(f"Warning: Could not process cache file {thumbnail_file}: {e}")

        except Exception as e:
            print(f"Warning: Cache cleanup failed: {e}")

    def clear_cache(self) -> bool:
        """Clear all thumbnails and best tomogram info from the cache.

        Returns:
            True if successful, False otherwise
        """
        try:
            if self.cache_dir and self.cache_dir.exists():
                # Remove all PNG files (thumbnails)
                for thumbnail_file in self.cache_dir.glob("*.png"):
                    thumbnail_file.unlink()

                # Remove all best tomogram info files
                for best_tomo_file in self.cache_dir.glob("*_best_tomogram.json"):
                    best_tomo_file.unlink()

                print("🧹 Cache cleared successfully")
                return True
            return False
        except Exception as e:
            print(f"Error clearing thumbnail cache: {e}")
            return False

    def get_cache_info(self) -> Dict[str, Any]:
        """Get information about the cache.

        Returns:
            Dictionary containing cache information
        """
        info = {
            "cache_dir": str(self.cache_dir) if self.cache_dir else None,
            "config_path": self.config_path,
            "config_hash": self.config_hash,
            "app_name": self.app_name,
            "thumbnail_count": 0,
            "cache_size_mb": 0.0,
        }

        # Skip expensive file scanning to avoid blocking - use fast check only
        if self.cache_dir and self.cache_dir.exists():
            try:
                # Quick directory listing without stat() calls to avoid blocking
                thumbnail_files = list(self.cache_dir.glob("*.png"))
                info["thumbnail_count"] = len(thumbnail_files)
                # Skip size calculation to avoid blocking on large caches
                info["cache_size_mb"] = 0.0  # Size calculation disabled for performance
            except Exception as e:
                print(f"⚠️ Error getting cache info: {e}")

        return info

    def save_best_tomogram_info(self, run_name: str, tomogram_type: str, voxel_spacing: float) -> bool:
        """Save information about the best tomogram selection for a run.

        Args:
            run_name: Name of the copick run
            tomogram_type: Type of the selected best tomogram
            voxel_spacing: Voxel spacing of the selected best tomogram

        Returns:
            True if successful, False otherwise
        """
        try:
            import time

            # Generate the cache key and thumbnail path for this best tomogram
            cache_key = self.get_cache_key(run_name, tomogram_type, voxel_spacing)
            thumbnail_path = self.get_thumbnail_path(cache_key)

            best_tomo_file = self.cache_dir / f"{run_name}_best_tomogram.json"
            best_tomo_info = {
                "run_name": run_name,
                "tomogram_type": tomogram_type,
                "voxel_spacing": voxel_spacing,
                "cache_key": cache_key,
                "thumbnail_path": str(thumbnail_path),
                "cached_at": str(time.time()),
            }

            with open(best_tomo_file, "w") as f:
                json.dump(best_tomo_info, f, indent=2)

            return True

        except Exception as e:
            print(f"❌ Error saving best tomogram info for '{run_name}': {e}")
            return False

    def load_best_tomogram_info(self, run_name: str) -> Optional[Dict[str, Any]]:
        """Load information about the best tomogram selection for a run.

        Args:
            run_name: Name of the copick run

        Returns:
            Dictionary with tomogram info if found, None otherwise
        """
        try:
            best_tomo_file = self.cache_dir / f"{run_name}_best_tomogram.json"

            if not best_tomo_file.exists():
                return None

            with open(best_tomo_file, "r") as f:
                best_tomo_info = json.load(f)

            return best_tomo_info

        except Exception as e:
            print(f"❌ Error loading best tomogram info for '{run_name}': {e}")
            return None

    def has_best_tomogram_info(self, run_name: str) -> bool:
        """Check if best tomogram information is cached for a run.

        Args:
            run_name: Name of the copick run

        Returns:
            True if best tomogram info is cached, False otherwise
        """
        try:
            best_tomo_file = self.cache_dir / f"{run_name}_best_tomogram.json"
            exists = best_tomo_file.exists()
            return exists
        except Exception as e:
            print(f"❌ Error checking best tomogram info for '{run_name}': {e}")
            return False

    def update_config(self, config_path: str) -> None:
        """Update the cache for a new config file.

        Args:
            config_path: Path to the new config file
        """
        if config_path != self.config_path:
            self.config_path = config_path
            self._setup_cache_directory()
            # Skip cache cleanup to avoid blocking main thread
            # self._cleanup_old_cache_entries()


class GlobalCacheManager:
    """Manager for global thumbnail cache instances."""

    def __init__(self):
        self._caches: Dict[str, ThumbnailCache] = {}

    def get_cache(self, app_name: str = "copick") -> ThumbnailCache:
        """Get a thumbnail cache instance for the given app name.

        Args:
            app_name: Name of the application

        Returns:
            ThumbnailCache instance
        """
        if app_name not in self._caches:
            self._caches[app_name] = ThumbnailCache(app_name=app_name)
        return self._caches[app_name]

    def set_cache_config(self, config_path: str, app_name: str = "copick") -> None:
        """Set the config path for a cache instance.

        Args:
            config_path: Path to the config file
            app_name: Name of the application
        """
        cache = self.get_cache(app_name)
        cache.update_config(config_path)


# Global cache manager instance
_global_cache_manager = GlobalCacheManager()


def get_global_cache(app_name: str = "copick") -> ThumbnailCache:
    """Get the global thumbnail cache instance.

    Args:
        app_name: Name of the application

    Returns:
        Global ThumbnailCache instance
    """
    return _global_cache_manager.get_cache(app_name)


def set_global_cache_config(config_path: str, app_name: str = "copick") -> None:
    """Set the config path for the global cache.

    Args:
        config_path: Path to the config file
        app_name: Name of the application
    """
    _global_cache_manager.set_cache_config(config_path, app_name)


def set_global_cache_image_interface(image_interface: ImageInterface, app_name: str = "copick") -> None:
    """Set the image interface for the global cache.

    Args:
        image_interface: Platform-specific image interface
        app_name: Name of the application
    """
    cache = _global_cache_manager.get_cache(app_name)
    cache.set_image_interface(image_interface)
