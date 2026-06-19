"""Behavioural guards for the MQTT connector.

These tests pin connector contracts that are easy to regress:

* subscriptions -- unsubscribe tears down the broker subscription and the
  per-topic state, and a topic's QoS tracks the running max of its live
  subscribers (it ratchets back down, not just up).
* callback dispatch -- subscriber callbacks run off the event-loop thread, so a
  callback may safely re-enter the connector (read/write) without deadlock.
* decoding -- each subscriber decodes a payload for its own node type, and
  decoding stays stable even after the owning node is garbage-collected.
* configuration -- ``qos``/``retain`` stay validated for the object's lifetime,
  and ``to_dict`` keeps ``*_env_var`` indirection.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import TimeoutError as FutureTimeoutError
import gc
import threading
from types import SimpleNamespace
from typing import Any

import pytest

from machine_data_model.nodes.connectors.abstract_connector import (
    AbstractConnector,
)
from machine_data_model.nodes.connectors.mqtt.mqtt_connector import (
    MqttConnector,
)
from machine_data_model.nodes.connectors.mqtt.mqtt_remote_resource_spec import (
    MqttRemoteResourceSpec,
)
from machine_data_model.nodes.connectors.remote_resource import RemoteResource
from machine_data_model.nodes.variable_node import (
    NumericalVariableNode,
    StringVariableNode,
)


class FakeClient:
    """Records publish/subscribe/unsubscribe calls made by the connector."""

    def __init__(self) -> None:
        self.published: list[dict[str, Any]] = []
        self.subscribed: list[dict[str, Any]] = []
        self.unsubscribed: list[str] = []

    async def publish(
        self,
        topic: str,
        payload: bytes,
        qos: int,
        retain: bool,
    ) -> None:
        self.published.append(
            {"topic": topic, "payload": payload, "qos": qos, "retain": retain}
        )

    async def subscribe(self, topic: str, qos: int) -> None:
        self.subscribed.append({"topic": topic, "qos": qos})

    async def unsubscribe(self, topic: str) -> None:
        self.unsubscribed.append(topic)


def _message(
    topic: str, payload: bytes, qos: int = 0, retain: bool = False
) -> SimpleNamespace:
    """Build a minimal aiomqtt-shaped message for ``_handle_message``."""
    return SimpleNamespace(
        topic=SimpleNamespace(value=topic),
        payload=payload,
        qos=qos,
        retain=retain,
    )


async def _deliver(
    connector: MqttConnector, topic: str, payload: bytes
) -> None:
    """Deliver a message on the connector's event loop (the listener path)."""
    connector._handle_message(_message(topic, payload))


class TestUnsubscribe:
    """Subscriptions can be torn down with the handle they hand out."""

    def test_abstract_connector_declares_unsubscribe(self) -> None:
        """``subscribe_to_node_changes`` promises an unsubscribe handle, so the
        abstract contract must declare its counterpart."""
        assert hasattr(AbstractConnector, "unsubscribe_from_node_changes")

    def test_unsubscribe_removes_callback_and_state(self) -> None:
        """Unsubscribing the last subscriber drops the broker subscription and
        the per-topic state instead of leaking it for the connector's life."""
        connector = MqttConnector(name="mqtt")
        fake_client = FakeClient()
        connector.client = fake_client
        try:
            handle = connector.subscribe_to_node_changes(
                RemoteResource(
                    "plant/temp", MqttRemoteResourceSpec(topic="plant/temp")
                ),
                lambda _value, _other: None,
            )
            connector._handle_message(_message("plant/temp", b"21.5"))

            connector.unsubscribe_from_node_changes(handle)

            assert fake_client.unsubscribed == ["plant/temp"]
            assert connector._topic_callbacks.get("plant/temp", {}) == {}
            assert "plant/temp" not in connector._topic_qos
            assert "plant/temp" not in connector._topic_payloads
        finally:
            connector.disconnect()


class TestCallbackDispatch:
    """Callbacks run off the event loop, so they may re-enter the connector."""

    def test_callback_does_not_run_on_event_loop_thread(self) -> None:
        """Callbacks are dispatched off the event-loop thread, so a callback
        that calls ``read_node_value``/``write_node_value`` cannot deadlock the
        loop."""
        connector = MqttConnector(name="mqtt")
        fake_client = FakeClient()
        connector.client = fake_client
        seen_thread: dict[str, Any] = {}
        try:
            connector.subscribe_to_node_changes(
                RemoteResource(
                    "plant/temp", MqttRemoteResourceSpec(topic="plant/temp")
                ),
                lambda _value, _other: seen_thread.__setitem__(
                    "thread", threading.current_thread()
                ),
            )
            # Drive the message through the listener path on the loop thread.
            connector._handle_task(_deliver(connector, "plant/temp", b"21.5"))

            assert seen_thread["thread"] is not connector._event_loop_thread
        finally:
            connector.disconnect()

    def test_reentrant_read_from_callback_does_not_deadlock(self) -> None:
        """A callback may re-enter the connector -- the data model does this via
        VariableNode notifications. Because delivery happens on the event loop
        (the listener path), the callback must run off it; otherwise its inner
        ``read_node_value`` submits a coroutine to the loop that is blocking on
        the callback.

        Delivery is scheduled with ``run_coroutine_threadsafe`` and awaited with
        a timeout so a regression surfaces as a bounded failure rather than a
        hung suite; teardown is skipped on deadlock to avoid joining a wedged
        daemon loop thread.
        """
        connector = MqttConnector(name="mqtt")
        fake_client = FakeClient()
        connector.client = fake_client
        result: dict[str, Any] = {}
        deadlocked = False

        def callback(_value: Any, _other: Any) -> None:
            result["read"] = connector.read_node_value(
                RemoteResource(
                    "plant/temp", MqttRemoteResourceSpec(topic="plant/temp")
                )
            )

        try:
            connector.subscribe_to_node_changes(
                RemoteResource(
                    "plant/temp", MqttRemoteResourceSpec(topic="plant/temp")
                ),
                callback,
            )

            future = asyncio.run_coroutine_threadsafe(
                _deliver(connector, "plant/temp", b"21.5"),
                connector._event_loop,
            )
            try:
                future.result(timeout=5.0)
            except FutureTimeoutError:
                deadlocked = True

            assert not deadlocked, "reentrant read from the callback deadlocked"
            assert result.get("read") == 21.5
        finally:
            if not deadlocked:
                connector.disconnect()


class TestQosRatchet:
    """A topic's QoS follows the running max of its live subscribers."""

    def test_qos_downgrades_when_high_qos_subscriber_leaves(self) -> None:
        """Two subscribers raise the topic to QoS 1; when the QoS-1 subscriber
        leaves, the topic is re-subscribed at the remaining max (QoS 0)."""
        connector = MqttConnector(name="mqtt")
        fake_client = FakeClient()
        connector.client = fake_client
        try:
            connector.subscribe_to_node_changes(
                RemoteResource(
                    "plant/temp",
                    MqttRemoteResourceSpec(topic="plant/temp", qos=0),
                ),
                lambda _v, _o: None,
            )
            high = connector.subscribe_to_node_changes(
                RemoteResource(
                    "plant/temp",
                    MqttRemoteResourceSpec(topic="plant/temp", qos=1),
                ),
                lambda _v, _o: None,
            )

            connector.unsubscribe_from_node_changes(high)

            assert connector._topic_qos["plant/temp"] == 0
            topic_subs = [
                s for s in fake_client.subscribed if s["topic"] == "plant/temp"
            ]
            assert topic_subs[-1]["qos"] == 0
        finally:
            connector.disconnect()


class TestSharedTopicDecoding:
    """Subscribers on a shared topic each decode for their own node type."""

    def test_two_nodes_on_one_topic_each_get_their_own_type(self) -> None:
        """A numeric and a string node share a topic; each callback receives the
        value decoded for its node type, not a single shared decode."""
        connector = MqttConnector(name="mqtt")
        fake_client = FakeClient()
        connector.client = fake_client

        numeric = NumericalVariableNode(name="Count", value=0)
        numeric.set_remote_path("plant/raw")
        text = StringVariableNode(name="Label", value="")
        text.set_remote_path("plant/raw")

        numeric_values: list[Any] = []
        string_values: list[Any] = []
        try:
            connector.subscribe_to_node_changes(
                RemoteResource.from_node(numeric),
                lambda value, _o: numeric_values.append(value),
            )
            connector.subscribe_to_node_changes(
                RemoteResource.from_node(text),
                lambda value, _o: string_values.append(value),
            )

            connector._handle_message(_message("plant/raw", b"10"))

            assert numeric_values == [10], "numeric node should decode int"
            assert string_values == ["10"], "string node should keep the string"
        finally:
            connector.disconnect()


class TestStableDecoding:
    """Decoding stays stable even after the owning node is collected."""

    def test_dropped_node_ref_keeps_string_decoding(self) -> None:
        """A StringVariableNode decodes payload "true" as the string "true";
        collecting the node must not flip that into the bool ``True``."""
        connector = MqttConnector(name="mqtt")
        fake_client = FakeClient()
        connector.client = fake_client

        node = StringVariableNode(name="Mode", value="")
        node.set_remote_path("plant/mode")
        resource = RemoteResource.from_node(node)
        values: list[Any] = []
        try:
            connector.subscribe_to_node_changes(
                resource, lambda value, _o: values.append(value)
            )

            # Node alive: decodes as the string "true".
            connector._handle_message(_message("plant/mode", b"true"))
            assert values[-1] == "true"

            # Node collected: the weakref goes dead, decoding must not flip.
            del node
            gc.collect()

            connector._handle_message(_message("plant/mode", b"true"))
            assert values[-1] == "true"
        finally:
            connector.disconnect()


class TestQosRetainValidation:
    """qos/retain stay validated after construction, not only in __init__."""

    def test_assigning_invalid_qos_is_rejected(self) -> None:
        connector = MqttConnector(name="mqtt")
        try:
            with pytest.raises((ValueError, TypeError)):
                connector.qos = 7
        finally:
            connector.disconnect()

    def test_assigning_invalid_retain_is_rejected(self) -> None:
        connector = MqttConnector(name="mqtt")
        try:
            with pytest.raises((ValueError, TypeError)):
                connector.retain = "yes"  # type: ignore[assignment]
        finally:
            connector.disconnect()


class TestToDictEnvVar:
    """to_dict preserves env-var indirection for a faithful round-trip."""

    def test_env_var_origin_survives_to_dict(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``ip_env_var`` serialises the env-var reference, not the resolved
        literal, so a dump/reload stays env-driven."""
        monkeypatch.setenv("MY_BROKER_HOST", "10.0.0.9")
        connector = MqttConnector(name="mqtt", ip_env_var="MY_BROKER_HOST")
        try:
            data = connector.to_dict()
            assert data.get("ip_env_var") == "MY_BROKER_HOST"
        finally:
            connector.disconnect()
