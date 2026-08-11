"""
Pytest configuration.

Adds src to sys.path for tests to import modules, while protecting stdlib imports
from being shadowed by src/code.py.
"""

import sys
import os


def pytest_configure(config):
    """Add src to sys.path after pytest initialization, protecting stdlib code module."""
    # By not using pythonpath in pyproject.toml, we ensure the stdlib code module
    # is already loaded before src/ is added to sys.path
    src_path = os.path.join(os.path.dirname(__file__), "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
