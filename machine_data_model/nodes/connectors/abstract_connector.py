import uuid
from abc import ABC, abstractmethod
from typing import Iterator

from machine_data_model.nodes.data_model_node import DataModelNode


class AbstractConnector(ABC):
    """
    Represents a generic connector/client.
    """

    def __init__(
        self,
        id: str | None = None,
        name: str | None = None,
        ip: str | None = None,
        port: int | None = None,
    ):
        self._id: str = str(uuid.uuid4()) if id is None else id
        self._name = name
        self._ip = ip
        self._port = port

    @property
    def id(self) -> str:
        return self._id

    @property
    def name(self) -> str | None:
        return self._name

    @property
    def ip(self) -> str | None:
        return self._ip

    @property
    def port(self) -> int | None:
        return self._port

    @abstractmethod
    async def connect(self) -> None:
        """
        Connect to the server.
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """
        Disconnect from the server.
        """
        pass

    @abstractmethod
    async def get_node(self, path: str) -> DataModelNode | None:
        """
        Try to retrieve the node from the server.
        """
        pass

    def __iter__(self) -> Iterator["AbstractConnector"]:
        for _ in []:
            yield _
