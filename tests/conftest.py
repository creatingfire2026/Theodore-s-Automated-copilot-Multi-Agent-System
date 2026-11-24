import os

import pytest


@pytest.fixture(autouse=True)
def _hermetic_sentinel_env(monkeypatch):
    """Tests must not pick up a sourced production sentinel.env (SENTINEL_REQUIRE_DISSENT_STORE=1 etc.)."""
    for name in [n for n in os.environ if n.startswith("SENTINEL_")]:
        monkeypatch.delenv(name)
