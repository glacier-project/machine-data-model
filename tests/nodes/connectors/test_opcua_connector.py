from collections.abc import Sequence
import math

from asyncua.sync import Server
from docker.models.containers import Container
import pytest

from machine_data_model.nodes.connectors.opcua_connector import OpcuaConnector
from tests import gen_random_string


class TestOpcuaConnector:
    @pytest.mark.parametrize(
        "name, ip, port, security_policy",
        [
            (
                gen_random_string(10),
                gen_random_string(10),
                10,
                gen_random_string(10),
            )
            for _ in range(3)
        ],
    )
    def test_opcua_connector(
        self,
        name: str,
        ip: str,
        port: int,
        security_policy: str,
    ) -> None:
        connector = OpcuaConnector(
            name=name, ip=ip, port=port, security_policy=security_policy
        )

        assert connector.name == name
        assert connector.ip == ip
        assert connector.port == port
        assert connector.security_policy == security_policy

    def test_connection(
        self,
        start_opcua_test_server: tuple[Container, int],
    ) -> None:
        docker_container, container_port = start_opcua_test_server
        connector = OpcuaConnector(
            name="myConnector",
            ip="127.0.0.1",
            port=container_port,
            security_policy="SecurityPolicyBasic256Sha256",
        )

        is_connected = connector.connect()
        assert is_connected, "connector should connect successfully"
        connector.disconnect()

    def test_read_node_value(
        self,
        start_opcua_test_server: tuple[Container, int],
    ) -> None:
        docker_container, container_port = start_opcua_test_server
        connector = OpcuaConnector(
            name="myConnector",
            ip="127.0.0.1",
            port=container_port,
            security_policy="SecurityPolicyBasic256Sha256",
        )

        is_connected = connector.connect()
        assert is_connected, "connector should connect successfully"

        with pytest.raises(ValueError, match="node does not exist"):
            connector.read_node_value("non_existent_node")

        temp_threshold_path = (
            "Objects/4:Boilers/4:Boiler #2/2:ParameterSet/"
            "4:OverheatedThresholdTemperature"
        )
        temp_threshold_value = connector.read_node_value(temp_threshold_path)
        assert (
            temp_threshold_value is not None
        ), "temp_threshold_value should not be None"

        asset_id_path = "Objects/4:Boilers/4:Boiler #2/2:AssetId"
        asset_id_value = connector.read_node_value(asset_id_path)
        assert asset_id_value is not None, "asset_id_value should not be None"

        connector.disconnect()

    def test_write_node_value(
        self,
        start_opcua_test_server: tuple[Container, int],
    ) -> None:
        docker_container, container_port = start_opcua_test_server
        connector = OpcuaConnector(
            name="myConnector",
            ip="127.0.0.1",
            port=container_port,
            security_policy="SecurityPolicyBasic256Sha256",
        )

        is_connected = connector.connect()
        assert is_connected, "connector should connect successfully"

        with pytest.raises(ValueError, match="node does not exist"):
            connector.write_node_value("non_existent_node", 123)

        temp_threshold_path = (
            "Objects/4:Boilers/4:Boiler #2/2:ParameterSet/"
            "4:OverheatedThresholdTemperature"
        )
        prev_temp_threshold_value = connector.read_node_value(
            temp_threshold_path
        )
        was_written = connector.write_node_value(
            temp_threshold_path, prev_temp_threshold_value + 7
        )
        assert was_written, "this node should have been written"
        current_temp_threshold_value = connector.read_node_value(
            temp_threshold_path
        )

        assert (
            current_temp_threshold_value == prev_temp_threshold_value + 7
        ), "the new value should be the previous value +7"

        connector.disconnect()

    def test_call_node_as_method(
        self,
        start_opcua_test_server: tuple[Container, int],
    ) -> None:
        docker_container, container_port = start_opcua_test_server
        connector = OpcuaConnector(
            name="myConnector",
            ip="127.0.0.1",
            port=container_port,
            security_policy="SecurityPolicyBasic256Sha256",
        )

        is_connected = connector.connect()
        assert is_connected, "connector should connect successfully"

        with pytest.raises(Exception, match="node doesn't exist"):
            connector.call_node_as_method("non_existent_node", {})

        add_method_path = "Objects/6:ReferenceTest/6:Methods/6:Methods_Add"
        add_method_result = connector.call_node_as_method(
            add_method_path, {"a": 2.0, "b": 3}
        )

        assert math.isclose(
            add_method_result, 5.0
        ), "the result should be 5.0 after adding 2.0 and 3"

        output_method_path = (
            "Objects/6:ReferenceTest/6:Methods/6:Methods_Output"
        )
        output_method_result = connector.call_node_as_method(
            output_method_path, {}
        )
        assert (
            output_method_result == "Output"
        ), "the return value of the output method should be the 'Output' string"

        connector.disconnect()

    def test_call_method_with_two_return_values(
        self, start_custom_opcua_server: tuple[Server, int]
    ) -> None:
        server, port = start_custom_opcua_server
        connector = OpcuaConnector(
            name="myConnector", ip="127.0.0.1", port=port
        )

        is_connected = connector.connect()
        assert is_connected, "connector should connect successfully"
        call_free_pallet_to_with_reservation_path = (
            "Objects/2:Methods/2:callFreePalletToWithReservation"
        )
        call_result = connector.call_node_as_method(
            call_free_pallet_to_with_reservation_path,
            {"destination": 5, "reservationId": 1},
        )

        assert isinstance(call_result, Sequence), "call_result should be a list"
        assert len(call_result) == 2, "call_result should return two values"
        assert isinstance(
            call_result[0], bool
        ), "call_result[0] should be a boolean"
        assert call_result[0], "call_result[0] should be always True"
        assert isinstance(
            call_result[1], int
        ), "call_result[1] should be an integer"
        assert (
            1 <= call_result[1] <= 10
        ), "call_result[1] should be between 1 and 10"
