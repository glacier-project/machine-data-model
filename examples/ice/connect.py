"""Example demonstrating OPC UA connector usage with ICE Laboratory machines.

This example shows how to:
- Load a data model with OPC UA connector configuration
- Inspect the loaded data model and connectors
- Call remote methods via OPC UA
- Handle connector lifecycle and cleanup

Configuration files:
- Cell4-opcua.yml: Robot coordinator PLC configuration
- Cell5-opcua.yml: Quality control configuration
- conveyor-opcua.yml: Conveyor belt configuration (default)
"""

import logging
from pathlib import Path
import sys

from machine_data_model.builder.data_model_builder import DataModelBuilder
from machine_data_model.data_model import DataModel

# Configuration options - change as needed
# Options: Cell4-opcua.yml, Cell5-opcua.yml, conveyor-opcua.yml
SELECTED_CONFIG = "conveyor-opcua.yml"
LOG_LEVEL = logging.INFO  # Change to logging.DEBUG for detailed debugging


def setup_logging() -> None:
    """Configure logging for the example.

    Sets up basic logging with the specified level and suppresses
    verbose asyncua library logs.
    """
    logging.basicConfig(
        stream=sys.stderr,
        level=LOG_LEVEL,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    # Suppress verbose OPC UA library logs
    logging.getLogger("asyncua").setLevel(logging.ERROR)


def load_data_model(config_file: str) -> DataModel:
    """Load the data model from the specified YAML configuration file.

    Args:
        config_file: Name of the YAML configuration file

    Returns:
        The loaded data model instance

    Raises:
        FileNotFoundError: If the configuration file doesn't exist
        Exception: If there's an error loading the data model
    """
    yml_path = Path(__file__).parent / config_file

    if not yml_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {yml_path}")

    print(f"\n{'='*60}")
    print(f"Loading data model from: {yml_path.name}")
    print(f"{'='*60}")

    builder = DataModelBuilder()
    data_model = builder.get_data_model(str(yml_path))

    print("✓ Data model loaded successfully")
    return data_model


def inspect_data_model(data_model) -> None:
    """Display information about the loaded data model and its connectors.

    Args:
        data_model: The data model instance to inspect
    """
    print(f"\n{'-'*60}")
    print("Data Model Overview:")
    print(f"{'-'*60}")
    print(
        f"  Name: {data_model.name if hasattr(data_model, 'name') else 'N/A'}"
    )
    print(
        f"  Root: {data_model.root if hasattr(data_model, 'root') else 'N/A'}"
    )

    print(f"\n{'-'*60}")
    print("Configured Connectors:")
    print(f"{'-'*60}")
    if hasattr(data_model, "connectors") and data_model.connectors:
        for i, connector in enumerate(data_model.connectors, 1):
            print(f"  {i}. {type(connector).__name__}")
            print(f"     {connector}")
    else:
        print("  No connectors configured")


def call_conveyor_method(data_model) -> None:
    """Example of calling a remote method via OPC UA.

    This demonstrates calling the setPalletDestination method on the
    conveyor system with specific parameters.

    Args:
        data_model: The data model instance with OPC UA connector
    """
    # Example node path for conveyor system
    method_path = (
        "/Objects/ConveyorHMI/ConveyorDataExchange/Commands/"
        "ConveyorCommandsPointer/setPalletDestination"
    )

    print(f"\n{'-'*60}")
    print("Calling Remote Method:")
    print(f"{'-'*60}")
    print(f"  Method: {method_path}")
    print("  Parameters: pallet_id=1, destination=15")

    try:
        node = data_model.get_node(method_path)
        result = node(1, 15)

        print("\n✓ Method call successful!")
        print(f"  Result: {result}")

    except KeyError as e:
        print(f"\n✗ Node not found: {e}")
        print("  Check that the node path exists in the data model")
    except Exception as e:
        print(f"\n✗ Method call failed: {e}")


def main() -> None:
    """Main entry point for the ICE OPC UA connector example.

    Demonstrates loading a data model with OPC UA connector,
    inspecting it, and calling remote methods.
    """
    setup_logging()

    data_model = None

    try:
        # Load the data model from YAML configuration
        data_model = load_data_model(SELECTED_CONFIG)

        # Display information about the data model
        inspect_data_model(data_model)

        # Example: Call a remote method (for conveyor configuration)
        if SELECTED_CONFIG == "conveyor-opcua.yml":
            call_conveyor_method(data_model)
        else:
            print(f"\n{'-'*60}")
            print(
                "NOTE: Method call example is configured for conveyor-opcua.yml"
            )
            print(
                "      Modify the example to call methods for other "
                "configurations"
            )
            print(f"{'-'*60}")

    except FileNotFoundError as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)

    except Exception as e:
        logging.exception("Unexpected error occurred")
        print(f"\n✗ Error: {e}")
        sys.exit(1)

    finally:
        # Always clean up connectors
        if data_model is not None and hasattr(data_model, "close_connectors"):
            print(f"\n{'-'*60}")
            print("Cleaning up connectors...")
            print(f"{'-'*60}")
            data_model.close_connectors()
            print("✓ Connectors closed successfully")


if __name__ == "__main__":
    main()
