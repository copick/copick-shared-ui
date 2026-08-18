"""Shared configuration for the copick-shared-ui test suite."""

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def isolated_thumbnail_cache(tmp_path, monkeypatch):
    """Keep worker cache creation and pruning inside pytest's temporary tree."""
    from copick_shared_ui.core import thumbnail_cache

    cache_root = tmp_path / "thumbnail-cache"

    def setup_cache_directory(cache):
        base_cache_dir = cache_root / cache.app_name / "thumbnails"
        if cache.config_path:
            cache.config_hash = cache._compute_config_hash(cache.config_path)
            cache.cache_dir = base_cache_dir / cache.config_hash
        else:
            cache.cache_dir = base_cache_dir / "default"

        cache.cache_dir.mkdir(parents=True, exist_ok=True)
        cache._ensure_metadata_file()

    manager = thumbnail_cache._global_cache_manager
    manager._caches.clear()
    monkeypatch.setattr(thumbnail_cache.ThumbnailCache, "_setup_cache_directory", setup_cache_directory)

    yield Path(cache_root)

    manager._caches.clear()
