"""Home Assistant tests: run with a venv that has
pytest-homeassistant-custom-component (``pytest tests_ha``)."""

from __future__ import annotations

import pathlib
import sys

import pytest

# The cloud stand-in lives with the pure tests.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tests"))


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield
