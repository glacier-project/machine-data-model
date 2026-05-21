"""Example CLI entry point for the machine data model package.

Loads a YAML data-model file and prints the resulting tree. Provided as a
smoke-test for the builder and protocol wiring rather than as a full CLI;
production users should import the library directly.

Usage:
    python -m machine_data_model [PATH_TO_YAML]

If ``PATH_TO_YAML`` is omitted, the script looks for ``template/data_model.yml``
relative to the current working directory.
"""

import argparse
from pathlib import Path
import sys

from machine_data_model.builder.data_model_builder import DataModelBuilder
from machine_data_model.protocols.frost_v1.frost_protocol_mng import (
    FrostProtocolMng,
)

DEFAULT_TEMPLATE = Path("template/data_model.yml")


def main(argv: list[str] | None = None) -> int:
    """Load a data-model YAML and print the resulting tree."""
    parser = argparse.ArgumentParser(
        prog="python -m machine_data_model",
        description="Load a YAML data model and print its tree.",
    )
    parser.add_argument(
        "yaml_path",
        nargs="?",
        type=Path,
        default=DEFAULT_TEMPLATE,
        help=(
            "Path to a data-model YAML file. "
            f"Defaults to {DEFAULT_TEMPLATE} relative to the working directory."
        ),
    )
    args = parser.parse_args(argv)

    if not args.yaml_path.is_file():
        parser.error(
            f"YAML file not found: {args.yaml_path}. "
            "Pass an explicit path or run from a directory containing "
            f"{DEFAULT_TEMPLATE}."
        )

    data_model_builder = DataModelBuilder()
    data_model = data_model_builder.get_data_model(str(args.yaml_path))
    protocol_mng = FrostProtocolMng(data_model=data_model)
    print(protocol_mng.get_data_model())
    return 0


if __name__ == "__main__":
    sys.exit(main())
