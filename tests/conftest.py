"""Top-level pytest configuration.

Auto-marks any test under ``tests/nodes/connectors`` or in the connector
builder/dumper test files with ``@pytest.mark.connector`` so the no-extras CI
job can deselect them via ``-m "not connector"`` without maintaining an
``--ignore`` list. Auto-marks tests under ``tests/exposers`` with
``@pytest.mark.exposer`` for the same reason.

Also registers the aiohttp pytest plugin globally so it is available for
async exposer tests (per pytest's rule that ``pytest_plugins`` must live in
the top-level conftest).
"""

from pathlib import Path

import pytest

pytest_plugins: list[str] = []

try:
    import aiohttp  # noqa: F401
except ImportError:
    pass
else:
    pytest_plugins.append("aiohttp.pytest_plugin")

_CONNECTOR_PATHS = (
    "tests/nodes/connectors",
    "tests/builder/test_data_model_builder_connectors.py",
    "tests/builder/test_data_model_dumper_connectors.py",
)

_EXPOSER_PATHS = ("tests/exposers",)


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Apply the ``connector`` and ``exposer`` markers to relevant tests."""
    repo_root = Path(__file__).resolve().parent.parent
    connector_marker = pytest.mark.connector
    exposer_marker = pytest.mark.exposer
    for item in items:
        try:
            rel = Path(item.fspath).resolve().relative_to(repo_root).as_posix()
        except ValueError:
            continue
        if any(rel.startswith(path) for path in _CONNECTOR_PATHS):
            item.add_marker(connector_marker)
        if any(rel.startswith(path) for path in _EXPOSER_PATHS):
            item.add_marker(exposer_marker)
