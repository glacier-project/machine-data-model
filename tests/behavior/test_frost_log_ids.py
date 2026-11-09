"""Peer-controlled ids never reach a log line with control characters."""

from dataclasses import replace
import logging

import pytest

from machine_data_model.behavior.condition import (
    Condition,
    WaitConditionOperator,
)
from machine_data_model.behavior.execution_error import (
    ExecutionError,
    ExecutionErrorCode,
)
from machine_data_model.data_model import DataModel
from machine_data_model.nodes.composite_method.composite_method_node import (
    CompositeMethodNode,
)
from machine_data_model.nodes.method_node import MethodNode
from machine_data_model.nodes.variable_node import NumericalVariableNode
from machine_data_model.protocols.frost_v1.frost_message import FrostMessage
from machine_data_model.protocols.frost_v1.frost_message_builder import (
    FrostMessageBuilder,
)
from machine_data_model.protocols.frost_v1.frost_payload import (
    ErrorCode,
)
from machine_data_model.protocols.frost_v1.frost_protocol_mng import (
    _MAX_LOGGED_ID,
    FrostProtocolMng,
    _log_id,
)
from tests.behavior import (
    composite,
    frost_request,
    frost_setup,
    wait_for_nonzero,
)

ESC = chr(0x1B)
EVIL = f"id1\nFORGED line{ESC}[31m\r\nmore"


def assert_clean(caplog: pytest.LogCaptureFixture) -> None:
    assert caplog.records
    for record in caplog.records:
        text = record.getMessage()
        for char in ("\n", "\r", ESC):
            assert char not in text, text


def invoke(node: str, correlation_id: str) -> FrostMessage:
    return replace(frost_request("dm", node), correlation_id=correlation_id)


class TestLogId:
    def test_plain_id_is_unchanged(self) -> None:
        assert _log_id("abc-123") == "abc-123"

    def test_control_characters_become_spaces(self) -> None:
        text = _log_id(EVIL)

        assert "\n" not in text and "\r" not in text and ESC not in text
        assert text.startswith("id1 FORGED line")

    def test_long_id_is_bounded(self) -> None:
        assert len(_log_id("x" * 5000)) <= _MAX_LOGGED_ID

    def test_non_string_is_accepted(self) -> None:
        assert _log_id(42) == "42"


class TestLoggedIds:
    def test_rejected_request_log(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        method = MethodNode(
            id="m",
            name="m",
            returns=[NumericalVariableNode(id="r", name="r", value=0)],
            callback=lambda **kwargs: 0,
            requires=[Condition("mode", WaitConditionOperator.EQ, 2)],
        )
        mode = NumericalVariableNode(id="mode", name="mode", value=1)
        data_model = DataModel(name="dm")
        data_model.root.add_child(mode)
        data_model.root.add_child(method)
        data_model._register_nodes(data_model.root)
        manager = FrostProtocolMng(data_model)

        with caplog.at_level(logging.DEBUG):
            manager.handle_request(invoke("m", EVIL))

        assert any("rejected" in r.getMessage() for r in caplog.records)
        assert_clean(caplog)

    def test_response_for_an_unknown_context(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        manager, _ = frost_setup()
        response = FrostMessageBuilder(
            sender="remote_dm"
        ).build_method_completed_message(
            target="dm", correlation_id=EVIL, ret={}, node="m"
        )

        with caplog.at_level(logging.DEBUG):
            manager.handle_response(response)

        assert any("unknown context" in r.getMessage() for r in caplog.records)
        assert_clean(caplog)

    def test_error_for_an_unknown_context(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        manager, _ = frost_setup()
        request = replace(frost_request("dm", "m"), correlation_id=EVIL)
        error = FrostMessageBuilder(sender="remote_dm").build_error_message(
            message=request, error_code=ErrorCode.NOT_ALLOWED, error_message="x"
        )

        with caplog.at_level(logging.DEBUG):
            manager.handle_error(error)

        assert any("unknown context" in r.getMessage() for r in caplog.records)
        assert_clean(caplog)

    def test_resume_of_an_unknown_context(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        manager, _ = frost_setup()

        with caplog.at_level(logging.DEBUG):
            assert manager._resume_composite_method(EVIL) is None

        assert_clean(caplog)

    def test_walk_up_log(self, caplog: pytest.LogCaptureFixture) -> None:
        manager, _ = frost_setup()

        with caplog.at_level(logging.DEBUG):
            manager._root_context_id(EVIL)

        assert_clean(caplog)

    def test_released_request_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        trigger = NumericalVariableNode(id="t", name="t", value=0)
        method = composite("m", [wait_for_nonzero(trigger)])
        manager, _ = frost_setup(method, variables=(trigger,))
        manager.handle_request(invoke("m", EVIL))
        (root_id,) = manager._running_methods
        method.delete_context(root_id)

        with caplog.at_level(logging.DEBUG):
            answer = manager._finish_if_terminated(root_id)

        assert answer is not None
        assert any("released" in r.getMessage() for r in caplog.records)
        assert_clean(caplog)

    def test_error_detail_log(self, caplog: pytest.LogCaptureFixture) -> None:
        method = CompositeMethodNode(name="m")
        manager, _ = frost_setup(method)
        request = invoke("m", EVIL)

        with caplog.at_level(logging.DEBUG):
            manager._create_execution_error_message(
                request,
                ExecutionError(ExecutionErrorCode.UNEXPECTED_ERROR, "boom"),
            )

        assert any("failed with" in r.getMessage() for r in caplog.records)
        assert_clean(caplog)
