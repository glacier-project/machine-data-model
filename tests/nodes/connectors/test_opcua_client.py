import pytest

from machine_data_model.nodes.connectors.opcua_connector import OpcuaConnector
from tests import gen_random_string


@pytest.mark.parametrize(
    "name, ip, port, security_policy",
    [
        (gen_random_string(10), gen_random_string(10), 10, gen_random_string(10))
        for _ in range(3)
    ],
)
class TestOpcuaConnector:
    def test_opcua_connector(
        self, name: str, ip: str, port: int, security_policy: str
    ) -> None:
        connector = OpcuaConnector(
            name=name, ip=ip, port=port, security_policy=security_policy
        )

        assert connector.name == name
        assert connector.ip == ip
        assert connector.port == port
        assert connector.security_policy == security_policy
