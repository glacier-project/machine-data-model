"""Top-level pytest configuration.

Auto-marks any test under ``tests/nodes/connectors`` or in the connector
builder/dumper test files with ``@pytest.mark.connector`` so the no-extras CI
job can deselect them via ``-m "not connector"`` without maintaining an
``--ignore`` list.
"""

from pathlib import Path

import pytest

_CONNECTOR_PATHS = (
    "tests/nodes/connectors",
    "tests/builder/test_data_model_builder_connectors.py",
    "tests/builder/test_data_model_dumper_connectors.py",
)


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Apply the ``connector`` marker to connector-dependent tests."""
    repo_root = Path(__file__).resolve().parent.parent
    connector_marker = pytest.mark.connector
    for item in items:
        try:
            rel = Path(item.fspath).resolve().relative_to(repo_root).as_posix()
        except ValueError:
            continue
        if any(rel.startswith(path) for path in _CONNECTOR_PATHS):
            item.add_marker(connector_marker)
