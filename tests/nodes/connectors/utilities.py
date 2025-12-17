import socket

from machine_data_model.builder.data_model_builder import DataModelBuilder
from machine_data_model.data_model import DataModel


def create_yaml_data_model(file_content: str) -> DataModel:
    """
    Uses the DataModelBuilder to create the data model starting from a string.
    """
    builder = DataModelBuilder()
    data_model = builder.from_string(file_content)
    return data_model


def free_port() -> int:
    """
    Creates a socket to get a free port number and then returns it.
    """
    sock = socket.socket()
    sock.bind(("", 0))
    port = sock.getsockname()[1]
    assert isinstance(port, int), "port must be an integer"
    sock.close()
    return port
