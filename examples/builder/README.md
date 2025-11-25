# Builder Examples

This folder contains small, well-designed examples demonstrating how to use the `DataModelBuilder` class in the machine-data-model library.

## Examples

### `basic_builder.py`

Demonstrates the fundamental usage of `DataModelBuilder` to load a data model from a YAML template and access its basic properties.

Run with:

```bash
python examples/builder/basic_builder.py
```

### `build_and_dump.py`

Shows how to build a data model from a template and serialize it back to a YAML file using `DataModelDumper`.

Run with:

```bash
python examples/builder/build_and_dump.py
```

### `inspect_nodes.py`

Illustrates how to traverse and inspect the nodes in a built data model, including their types and properties.

Run with:

```bash
python examples/builder/inspect_nodes.py
```

## Prerequisites

- Ensure the required dependencies are installed (see `requirements.txt`, `requirements-dev.txt`, and `pyproject.toml`).
- Templates like `template/data_model.yml` and `template/simple_model.yaml` should exist in the project root.

These examples follow the project's coding guidelines, including PEP 8 style, comprehensive docstrings, and type hints.
