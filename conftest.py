"""Pytest configuration."""

import pytest


def pytest_collection_modifyitems(config, items):
    """Modify collected test items to exclude non-test functions from source files."""
    filtered_items = []
    for item in items:
        # Exclude functions that are imported from motioneye package
        # These are utility/source functions, not actual tests
        if hasattr(item, 'obj') and hasattr(item.obj, '__module__'):
            # Skip functions from motioneye.* modules (source code)
            # Only include actual test functions from tests/ directory
            if item.obj.__module__.startswith('motioneye.'):
                continue
        filtered_items.append(item)
    items[:] = filtered_items
