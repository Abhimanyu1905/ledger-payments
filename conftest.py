"""Root conftest - sets event loop policy before pytest-asyncio initializes."""

import asyncio
import sys


def pytest_configure(config):
    """Set event loop policy before any async tests run."""
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
