"""Load pure integration modules without importing Home Assistant runtime code."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).parents[1]
PACKAGE = ROOT / "custom_components" / "iotrix"


def load(name: str) -> ModuleType:
    """Import a pure module while bypassing custom_components.iotrix.__init__."""
    if "custom_components" not in sys.modules:
        namespace = ModuleType("custom_components")
        namespace.__path__ = [str(ROOT / "custom_components")]  # type: ignore[attr-defined]
        sys.modules["custom_components"] = namespace
    if "custom_components.iotrix" not in sys.modules:
        package = ModuleType("custom_components.iotrix")
        package.__path__ = [str(PACKAGE)]  # type: ignore[attr-defined]
        sys.modules["custom_components.iotrix"] = package
    return importlib.import_module(f"custom_components.iotrix.{name}")
