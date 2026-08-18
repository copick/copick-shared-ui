"""Package import smoke tests."""

import importlib
import pkgutil

import copick_shared_ui
from copick_shared_ui.core.thumbnail_cache import get_global_cache


def test_every_package_module_imports():
    module_names = [
        module.name for module in pkgutil.walk_packages(copick_shared_ui.__path__, prefix="copick_shared_ui.")
    ]

    assert module_names
    for module_name in module_names:
        importlib.import_module(module_name)


def test_global_thumbnail_cache_is_isolated(isolated_thumbnail_cache):
    cache = get_global_cache()

    assert cache.cache_dir.is_relative_to(isolated_thumbnail_cache)
