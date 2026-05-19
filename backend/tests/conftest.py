"""Pytest conftest shim importing fixtures from `fixtures.py`."""

import importlib.util
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
fixtures_path = TESTS_DIR / "test_fixtures.py"
spec = importlib.util.spec_from_file_location("tests_fixtures", str(fixtures_path))
if spec and spec.loader:
    fixtures_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixtures_mod)
    for name, val in vars(fixtures_mod).items():
        if not name.startswith("_"):
            globals()[name] = val
else:
    raise ImportError(f"Could not load fixtures from {fixtures_path}")
