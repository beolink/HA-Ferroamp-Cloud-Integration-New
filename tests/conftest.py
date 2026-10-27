"""Register package stubs so the pure modules import without Home Assistant."""

from __future__ import annotations

import pathlib
import sys
import types

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_CC = _ROOT / "custom_components"
_PKG = _CC / "ferroamp_cloud_control"

for _name, _path in (("custom_components", _CC), ("custom_components.ferroamp_cloud_control", _PKG)):
    if _name not in sys.modules:
        _mod = types.ModuleType(_name)
        _mod.__path__ = [str(_path)]
        sys.modules[_name] = _mod
