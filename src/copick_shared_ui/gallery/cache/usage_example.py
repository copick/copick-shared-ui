"""Usage examples for the cross-platform thumbnail cache system."""

from typing import Any, Optional

from .thumbnail_cache import ThumbnailCache, get_global_cache, set_global_cache_config
from .image_interfaces import create_image_interface, QtImageInterface, NumpyImageInterface


def chimerax_usage_example():
    """Example usage for ChimeraX with Qt."""
    # Create a cache instance specifically for ChimeraX
    cache = ThumbnailCache(app_name="ChimeraX")
    
    # Set up Qt image interface
    image_interface = create_image_interface("qt")  # or QtImageInterface()
    cache.set_image_interface(image_interface)
    
    # Set config path if available
    config_path = "/path/to/copick/config.json"
    cache.update_config(config_path)
    
    # Generate cache key
    cache_key = cache.get_cache_key("run_001", "wbp", 10.0)
    
    # Check if thumbnail exists
    if cache.has_thumbnail(cache_key):
        # Load existing thumbnail
        thumbnail = cache.load_thumbnail(cache_key)  # Returns QPixmap
        if thumbnail:
            print("Loaded thumbnail from cache")
    else:
        # Create new thumbnail (example with QPixmap)
        from Qt.QtGui import QPixmap
        new_thumbnail = QPixmap(128, 128)
        new_thumbnail.fill()  # Fill with default color
        
        # Save to cache
        if cache.save_thumbnail(cache_key, new_thumbnail):
            print("Saved thumbnail to cache")
    
    # Get cache information
    cache_info = cache.get_cache_info()
    print(f"Cache directory: {cache_info['cache_dir']}")
    print(f"Thumbnail count: {cache_info['thumbnail_count']}")
    print(f"Cache size: {cache_info['cache_size_mb']:.2f} MB")


def napari_usage_example():
    """Example usage for napari with numpy arrays."""
    # Create a cache instance specifically for napari
    cache = ThumbnailCache(app_name="napari")
    
    # Set up numpy image interface
    image_interface = create_image_interface("numpy")  # or NumpyImageInterface()
    cache.set_image_interface(image_interface)
    
    # Set config path if available
    config_path = "/path/to/copick/config.json"
    cache.update_config(config_path)
    
    # Generate cache key
    cache_key = cache.get_cache_key("run_002", "denoised", 5.0)
    
    # Check if thumbnail exists
    if cache.has_thumbnail(cache_key):
        # Load existing thumbnail
        thumbnail = cache.load_thumbnail(cache_key)  # Returns numpy array
        if thumbnail is not None:
            print(f"Loaded thumbnail from cache: {thumbnail.shape}")
    else:
        # Create new thumbnail (example with numpy array)
        import numpy as np
        new_thumbnail = np.random.randint(0, 256, (128, 128, 3), dtype=np.uint8)
        
        # Save to cache
        if cache.save_thumbnail(cache_key, new_thumbnail):
            print("Saved thumbnail to cache")
    
    # Get cache information
    cache_info = cache.get_cache_info()
    print(f"Cache directory: {cache_info['cache_dir']}")
    print(f"Thumbnail count: {cache_info['thumbnail_count']}")
    print(f"Cache size: {cache_info['cache_size_mb']:.2f} MB")


def global_cache_usage_example():
    """Example usage with global cache instances."""
    # Use global cache for ChimeraX
    chimerax_cache = get_global_cache("ChimeraX")
    chimerax_cache.set_image_interface(create_image_interface("qt"))
    
    # Use global cache for napari
    napari_cache = get_global_cache("napari")
    napari_cache.set_image_interface(create_image_interface("numpy"))
    
    # Set config for both caches
    config_path = "/path/to/copick/config.json"
    set_global_cache_config(config_path, "ChimeraX")
    set_global_cache_config(config_path, "napari")
    
    # Both caches will use the same underlying cache directory structure
    # but have different image interfaces
    print("ChimeraX cache info:", chimerax_cache.get_cache_info())
    print("napari cache info:", napari_cache.get_cache_info())


def migration_from_chimerax_example():
    """Example showing how to migrate from the old ChimeraX-specific cache."""
    # Old way (ChimeraX-specific)
    # from chimerax_copick.io.thumbnail_cache import ThumbnailCache as OldCache
    # old_cache = OldCache(config_path)
    
    # New way (shared, platform-agnostic)
    new_cache = ThumbnailCache(app_name="ChimeraX")
    new_cache.set_image_interface(create_image_interface("qt"))
    
    # The cache directory structure and functionality remain the same
    # Only the image handling is abstracted
    cache_key = new_cache.get_cache_key("run_001", "wbp", 10.0)
    
    # The same cache files will be accessible
    if new_cache.has_thumbnail(cache_key):
        print("Existing cache files are still accessible")


if __name__ == "__main__":
    print("ChimeraX usage example:")
    chimerax_usage_example()
    
    print("\nnapari usage example:")
    napari_usage_example()
    
    print("\nGlobal cache usage example:")
    global_cache_usage_example()
    
    print("\nMigration example:")
    migration_from_chimerax_example()