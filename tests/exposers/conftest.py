"""Shared fixtures for exposer tests.

All tests in this directory require the ``http`` optional extra;
``pytest.importorskip`` ensures the module is skipped cleanly if
aiohttp is not installed.
"""

import pytest

pytest.importorskip("aiohttp")

pytest_plugins = ["aiohttp.pytest_plugin"]
