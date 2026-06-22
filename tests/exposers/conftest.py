"""Shared fixtures for exposer tests.

All tests in this directory require the ``http`` optional extra;
``pytest.importorskip`` ensures the module is skipped cleanly if
aiohttp is not installed. The aiohttp pytest plugin is registered in
the top-level ``tests/conftest.py``.
"""

import pytest

pytest.importorskip("aiohttp")
