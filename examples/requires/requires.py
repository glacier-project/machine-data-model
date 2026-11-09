"""Try the preconditions of examples/requires/requires.yml.

Run it from the root of the repository:

    python examples/requires/requires.py
"""

from pathlib import Path

from machine_data_model.builder.data_model_builder import DataModelBuilder
from machine_data_model.nodes.composite_method.composite_method_node import (
    CompositeMethodNode,
)
from machine_data_model.nodes.variable_node import VariableNode


def main() -> None:
    """Load the model in strict mode and call the methods."""
    path = Path(__file__).with_name("requires.yml")
    # strict_requires makes loading fail if a call node forgets on_unmet.
    data_model = DataModelBuilder(strict_requires=True).get_data_model(
        str(path)
    )

    def node(name: str) -> CompositeMethodNode:
        found = data_model.get_node(f"/plant/{name}")
        assert isinstance(found, CompositeMethodNode)
        return found

    def variable(name: str) -> VariableNode:
        found = data_model.get_node(f"/plant/{name}")
        assert isinstance(found, VariableNode)
        return found

    mode, state = variable("mode"), variable("state")
    start = node("start")

    print("start.is_executable():", start.is_executable())
    for outcome in start.evaluate_requires():
        print("  ", outcome.result.value, "-", outcome.message)

    result = node("start_now")()
    print(
        "start_now while not ready ->",
        result.error.code if result.error else "ok",
    )

    pending = node("start_when_ready")()
    print(
        "start_when_ready while not ready -> pending",
        list(pending.return_values),
    )

    mode.write(2)
    print("mode set to 2, start.is_executable():", start.is_executable())
    print(
        "start_now ->",
        node("start_now")().error or "ok",
        "state =",
        state.read(),
    )


if __name__ == "__main__":
    main()
