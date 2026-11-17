import os

import pytest


@pytest.fixture(autouse=True)
def isolated_environment():
    """Restore os.environ after each test: the CLI loads .env files into it."""
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
