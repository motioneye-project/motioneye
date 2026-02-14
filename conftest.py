"""Pytest configuration."""

import pytest


def pytest_collection_modifyitems(config, items):
    """Modify collected test items to exclude non-test functions from source files."""
    filtered_items = []
    for item in items:
        # Exclude functions that are imported from motioneye.utils
        # These are utility functions, not actual tests
        if hasattr(item, 'obj') and hasattr(item.obj, '__module__'):
            # Skip functions from motioneye.utils.* modules
            if item.obj.__module__.startswith('motioneye.utils.'):
                continue
        filtered_items.append(item)
    items[:] = filtered_items
