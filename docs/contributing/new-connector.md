# Adding a new connector

This walks through everything you need to do to add a new connector
(say, for a hypothetical `foo` protocol) to `machine-data-model`. The
project uses a plugin-style registry, so the builder and dumper never
hard-code connector classes — they look them up by name.

## 1. Pick a name

Decide on the short, lower-case name you want the connector to use
everywhere (e.g. `foo`). This name is the YAML tag stem, the optional
extra name, the pytest marker (already shared, see below), and the
registry key.

## 2. Create the subpackage

Add a new subpackage under `machine_data_model/nodes/connectors/foo/`
with the following layout:

```
machine_data_model/nodes/connectors/foo/
    __init__.py
    foo_connector.py
    foo_remote_resource_spec.py
    _yaml.py
```

- `foo_connector.py` — the concrete `AbstractConnector` (or
  `AbstractAsyncConnector`) subclass that talks to the remote system.
- `foo_remote_resource_spec.py` — the
  `AbstractRemoteResourceSpec` subclass describing per-node config.
- `_yaml.py` — the YAML constructor and representer pair for the two
  classes. Use the `build_kwargs` helper from
  `machine_data_model.nodes.connectors._yaml_helpers` to validate
  YAML keys against your constructor's named parameters.

## 3. Self-register in `__init__.py`

The package's `__init__.py` is where everything is wired up. The
pattern is: try to import the implementation; on success register a
`ConnectorPlugin`, on `ImportError` register an `UnavailableConnector`
that points users at the right `pip install` hint.

```python
"""Foo connector subpackage."""

from machine_data_model.nodes.connectors.registry import (
    ConnectorPlugin,
    UnavailableConnector,
    register_connector,
    register_unavailable,
)

try:
    from .foo_connector import FooConnector
    from .foo_remote_resource_spec import FooRemoteResourceSpec
    from ._yaml import (
        construct_foo_connector,
        construct_foo_remote_resource_spec,
        represent_foo_connector,
        represent_foo_remote_resource_spec,
    )
except ImportError:
    register_unavailable(
        UnavailableConnector(
            name="foo",
            yaml_tag_classes=("FooConnector", "FooRemoteResourceSpec"),
            install_hint="pip install machine-data-model[foo]",
        )
    )
    __all__: list[str] = []
else:
    register_connector(
        ConnectorPlugin(
            name="foo",
            connector_cls=FooConnector,
            spec_cls=FooRemoteResourceSpec,
            construct_connector=construct_foo_connector,
            construct_spec=construct_foo_remote_resource_spec,
            represent_connector=represent_foo_connector,
            represent_spec=represent_foo_remote_resource_spec,
        )
    )
    __all__ = ["FooConnector", "FooRemoteResourceSpec"]
```

There is **no other wiring** needed for the builder/dumper to find the
new connector. `discover_connectors()` in
`machine_data_model.nodes.connectors.registry` imports every subpackage
at builder/dumper construction time, so your `__init__.py` runs and
self-registers automatically.

## 4. Add the optional extra

In `pyproject.toml`, add a new entry under
`[project.optional-dependencies]`:

```toml
foo = ["foo-client>=1.0,<2"]
all = ["machine-data-model[opcua,mqtt,foo]"]
```

Then refresh the lockfile with `uv lock`.

## 5. Add tests

Place connector-only tests under
`tests/nodes/connectors/foo/`. Add an empty `__init__.py` for pytest
package consistency, and start each test module with
`pytest.importorskip("foo_client")` so the no-extras CI job still
collects cleanly.

The `connector` pytest marker is applied automatically by
`tests/conftest.py` based on file path — you don't need to mark tests
by hand. The no-extras CI job runs `pytest -m "not connector"` so your
tests are skipped there.

If you want builder/dumper integration tests, add them to
`tests/builder/test_data_model_builder_connectors.py` and
`tests/builder/test_data_model_dumper_connectors.py` — those files are
already on the `connector`-marker auto-list.

## 6. Verify

```bash
uv sync --all-extras --all-groups
uv run pytest tests/nodes/connectors/foo/         # full coverage
uv run pytest -m "not connector"                  # no-extras path
uv run pyrefly check machine_data_model tests
```

## Reference

- `machine_data_model/nodes/connectors/registry.py` — the registry
  module's docstring is the canonical description of the registration
  API.
- `machine_data_model/nodes/connectors/mqtt/__init__.py` and
  `.../opcua/__init__.py` — working examples of the
  registration pattern.
- `machine_data_model/nodes/connectors/_yaml_helpers.py` — shared
  YAML construction helpers (currently just `build_kwargs`).
