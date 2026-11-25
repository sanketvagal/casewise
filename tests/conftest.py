import os

import pytest


@pytest.fixture(autouse=True)
def isolated_environment():
    """Restore os.environ after each test: the CLI loads .env files into it.

    API keys are blanked first. The CLI's .env loading never overrides a variable that
    is already set, so no test can reach a live provider with the developer's real keys,
    even one that runs the CLI in record mode against the repo's real data.
    """
    saved = dict(os.environ)
    os.environ["GROQ_API_KEY"] = ""
    os.environ["GEMINI_API_KEY"] = ""
    yield
    os.environ.clear()
    os.environ.update(saved)
