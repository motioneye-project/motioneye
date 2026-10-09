"""Pytest configuration."""


def pytest_collection_modifyitems(items):
    """Exclude test functions imported from outside the tests package."""
    items[:] = [
        item
        for item in items
        if not hasattr(item, 'obj')
        or not callable(item.obj)
        or item.obj.__module__ == 'tests'
        or item.obj.__module__.startswith('tests.')
    ]
