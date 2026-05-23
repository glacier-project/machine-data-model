"""All benchmark-framework tests need aiohttp transitively."""

import pytest

pytest.importorskip("aiohttp")
