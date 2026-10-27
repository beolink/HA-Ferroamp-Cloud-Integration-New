"""Home Assistant tests: run with a venv that has
pytest-homeassistant-custom-component (``pytest tests_ha``)."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield
