import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import logging
import threading
from typing import Any

import aiomqtt
from typing_extensions import override

from machine_data_model.nodes.connectors.abstract_async_connector import (
    AbstractAsyncConnector,
)
from machine_data_model.nodes.connectors.abstract_connector import (
    SubscriptionArguments,
)
from machine_data_model.nodes.connectors.remote_resource import RemoteResource

from .mqtt_payload_codec import (
    MqttPayloadCodec,
    MqttPayloadDeserializer,
    MqttPayloadSerializer,
    get_mqtt_payload_codec,
    normalize_mqtt_payload,
)
from .mqtt_remote_resource_spec import (
    MqttRemoteResourceSpec,
    join_topic,
    validate_topic,
)

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MqttSubscriptionArguments(SubscriptionArguments):
    """Data returned to the MQTT subscription callback."""

    topic: str
    payload: bytes
    qos: int
    retain: bool


@dataclass
class _MqttSubscription:
    """Per-subscriber state kept for a single ``subscribe_to_node_changes``."""

    topic: str
    callback: Callable[[Any, MqttSubscriptionArguments], None]
    resource: RemoteResource
    qos: int


class MqttConnector(AbstractAsyncConnector):
    """Represents an MQTT client."""

    def __init__(
        self,
        id: str | None = None,
        name: str | None = None,
        ip: str | None = "127.0.0.1",
        ip_env_var: str | None = None,
        port: int | None = 1883,
        port_env_var: str | None = None,
        username: str | None = None,
        username_env_var: str | None = None,
        password: str | None = None,
        password_env_var: str | None = None,
        client_id: str | None = None,
        topic_prefix: str | None = None,
        keepalive: int = 60,
        qos: int = 0,
        retain: bool = False,
        payload_codec: str | MqttPayloadCodec = "string",
        payload_serializer: MqttPayloadSerializer | None = None,
        payload_deserializer: MqttPayloadDeserializer | None = None,
    ) -> None:
        """Initializes an MQTT client."""
        super().__init__(
            id=id,
            name=name,
            ip=ip,
            ip_env_var=ip_env_var,
            port=port,
            port_env_var=port_env_var,
            username=username,
            username_env_var=username_env_var,
            password=password,
            password_env_var=password_env_var,
        )
        self.client_id = client_id
        self.topic_prefix = topic_prefix
        self.keepalive = keepalive
        self.qos = qos
        self.retain = retain
        self._payload_codec = ""
        self._payload_serializer: MqttPayloadSerializer
        self._payload_deserializer: MqttPayloadDeserializer
        self.payload_codec = payload_codec
        if payload_serializer is not None:
            self.payload_serializer = payload_serializer
        if payload_deserializer is not None:
            self.payload_deserializer = payload_deserializer
        self.client: Any | None = None
        self._client_context: Any | None = None
        self._listener_task: asyncio.Task[None] | None = None
        self._topic_payloads: dict[str, bytes] = {}
        self._topic_callbacks: dict[str, dict[int, _MqttSubscription]] = {}
        self._subscription_topics: dict[int, str] = {}
        self._topic_qos: dict[str, int] = {}
        self._next_subscription_id = 1
        self._callback_executor: ThreadPoolExecutor | None = None

    @property
    def qos(self) -> int:
        """Return the default MQTT QoS used for publishes and subscriptions."""
        return self._qos

    @qos.setter
    def qos(self, value: int) -> None:
        """Validate and store the default MQTT QoS."""
        if value not in (0, 1, 2):
            raise ValueError("MQTT QoS must be 0, 1, or 2")
        self._qos = value

    @property
    def retain(self) -> bool:
        """Return the default MQTT retain flag used for publishes."""
        return self._retain

    @retain.setter
    def retain(self, value: bool) -> None:
        """Validate and store the default MQTT retain flag."""
        if not isinstance(value, bool):
            raise TypeError("MQTT retain must be a bool")
        self._retain = value

    @override
    async def _async_connect(self) -> bool:
        """Asynchronously connects to the MQTT broker."""
        client = aiomqtt.Client(
            hostname=self.ip or "127.0.0.1",
            port=self.port or 1883,
            username=self.username,
            password=self.password,
            identifier=self.client_id,
            keepalive=self.keepalive,
        )
        client_context_entered = False
        try:
            self.client = await client.__aenter__()
            self._client_context = client
            client_context_entered = True
            self._listener_task = asyncio.create_task(
                self._listen_for_messages()
            )
            for topic in self._topic_callbacks:
                await self.client.subscribe(
                    topic,
                    qos=self._topic_qos.get(topic, self.qos),
                )
        except Exception as exp:
            _logger.error(
                f"Couldn't connect the '{self.name}' connector to the MQTT "
                f"broker"
            )
            _logger.error(exp)
            if client_context_entered:
                await self._close_client_context()
            self.client = None
            self._client_context = None
            return False
        _logger.debug(f"Connected the '{self.name}' connector to MQTT broker")
        return True

    @override
    async def _async_disconnect(self) -> bool:
        """Asynchronously disconnects from the MQTT broker."""
        await self._cancel_listener_task()
        self._shutdown_callback_executor()

        if self._client_context is None:
            self.client = None
            return True

        try:
            await self._client_context.__aexit__(None, None, None)
        except Exception as exp:
            _logger.error(f"Couldn't disconnect '{self.name}' connector")
            _logger.error(exp)
            return False
        finally:
            self.client = None
            self._client_context = None

        return True

    async def _close_client_context(self) -> None:
        """Best-effort cleanup for partially connected clients."""
        await self._cancel_listener_task()
        if self._client_context is None:
            return
        try:
            await self._client_context.__aexit__(None, None, None)
        except Exception as exp:
            _logger.error(f"Couldn't close '{self.name}' MQTT client context")
            _logger.error(exp)

    async def _cancel_listener_task(self) -> None:
        """Cancel the background MQTT listener task."""
        if self._listener_task is None:
            return
        self._listener_task.cancel()
        try:
            await self._listener_task
        except asyncio.CancelledError:
            pass
        except Exception as exp:
            _logger.error(
                f"MQTT listener for '{self.name}' stopped with an error"
            )
            _logger.error(exp)
        finally:
            self._listener_task = None

    @override
    async def _async_get_remote_resource(self, resource: RemoteResource) -> str:
        """Resolve the MQTT subscription topic."""
        return self._resolve_subscribe_topic(resource)

    @override
    async def _async_read_node_value(self, resource: RemoteResource) -> Any:
        """Return the last MQTT value received for this node's topic."""
        topic = self._resolve_subscribe_topic(resource)
        payload = self._topic_payloads.get(topic)
        if payload is None:
            return None
        return self.deserialize_value(payload, resource)

    @override
    async def _async_write_node_value(
        self,
        resource: RemoteResource,
        value: Any,
    ) -> bool:
        """Publish a scalar value to the node's MQTT topic."""
        if self.client is None:
            raise RuntimeError(
                f"Couldn't publish '{resource.path}' using '{self.name}' "
                "connector: the client is not connected"
            )
        topic = self._resolve_publish_topic(resource)
        payload = self.serialize_value(value, resource)
        qos = self._resolve_qos(resource)
        retain = self._resolve_retain(resource)
        try:
            await self.client.publish(
                topic,
                payload=payload,
                qos=qos,
                retain=retain,
            )
        except Exception as exp:
            _logger.error(
                f"Failed to publish node '{resource.path}' to MQTT topic "
                f"'{topic}'"
            )
            _logger.error(exp)
            return False
        return True

    @override
    async def _async_call_node_as_method(
        self,
        resource: RemoteResource,
        kwargs: dict[str, Any],
    ) -> Any:
        """MQTT method calls are not supported yet."""
        raise NotImplementedError("MQTT connector does not support methods yet")

    @override
    async def _async_subscribe_to_node_changes(
        self,
        resource: RemoteResource,
        callback: Callable[[Any, MqttSubscriptionArguments], None],
    ) -> int:
        """Subscribe to MQTT messages for the node's topic."""
        if self.client is None:
            raise RuntimeError(
                f"Couldn't subscribe to '{resource.path}' using '{self.name}' "
                "connector: the client is not connected"
            )
        topic = self._resolve_subscribe_topic(resource)
        subscription_id = self._next_subscription_id
        self._next_subscription_id += 1

        callbacks = self._topic_callbacks.setdefault(topic, {})
        first_subscription = len(callbacks) == 0
        requested_qos = self._resolve_qos(resource)
        callbacks[subscription_id] = _MqttSubscription(
            topic=topic,
            callback=callback,
            resource=resource,
            qos=requested_qos,
        )
        self._subscription_topics[subscription_id] = topic
        previous_qos = self._topic_qos.get(topic)
        qos = (
            requested_qos
            if previous_qos is None
            else max(previous_qos, requested_qos)
        )
        self._topic_qos[topic] = qos
        if first_subscription or qos != previous_qos:
            await self.client.subscribe(
                topic,
                qos=qos,
            )
        return subscription_id

    @override
    async def _async_unsubscribe_from_node_changes(self, handle: int) -> bool:
        """Remove a subscription and adjust the topic's broker state."""
        topic = self._subscription_topics.pop(handle, None)
        if topic is None:
            return False
        callbacks = self._topic_callbacks.get(topic, {})
        callbacks.pop(handle, None)

        if callbacks:
            # Other subscribers remain: re-subscribe at the new maximum QoS,
            # which may be lower than before (QoS now ratchets down too).
            new_qos = max(sub.qos for sub in callbacks.values())
            if new_qos != self._topic_qos.get(topic):
                self._topic_qos[topic] = new_qos
                if self.client is not None:
                    await self.client.subscribe(topic, qos=new_qos)
            return True

        # Last subscriber left: drop the broker subscription and per-topic
        # state instead of leaking it for the connector's lifetime.
        if self.client is not None:
            await self.client.unsubscribe(topic)
        self._topic_callbacks.pop(topic, None)
        self._topic_qos.pop(topic, None)
        self._topic_payloads.pop(topic, None)
        return True

    async def _listen_for_messages(self) -> None:
        """Consume MQTT messages and dispatch callbacks."""
        if self.client is None or not isinstance(self.client, aiomqtt.Client):
            return

        messages = self.client.messages
        if callable(messages):
            messages = messages()

        try:
            async for message in messages:  # pyrefly: ignore[not-iterable]
                self._handle_message(message)
        except asyncio.CancelledError:
            raise
        except Exception as exp:
            _logger.error(f"MQTT listener for '{self.name}' failed")
            _logger.error(exp)

    def _handle_message(self, message: Any) -> None:
        """Decode one MQTT message and notify registered callbacks."""
        topic = self._message_topic(message)
        payload = self._message_payload(message)
        self._topic_payloads[topic] = payload
        other = MqttSubscriptionArguments(
            topic=topic,
            payload=payload,
            qos=int(getattr(message, "qos", 0)),
            retain=bool(getattr(message, "retain", False)),
        )
        subscriptions = list(self._topic_callbacks.get(topic, {}).values())
        self._dispatch_subscriptions(subscriptions, payload, other, topic)

    def _dispatch_subscriptions(
        self,
        subscriptions: list[_MqttSubscription],
        payload: bytes,
        other: MqttSubscriptionArguments,
        topic: str,
    ) -> None:
        """Run subscription callbacks, off the event loop when necessary."""
        if not subscriptions:
            return
        if threading.current_thread() is self._event_loop_thread:
            # The listener runs on the event loop. Dispatch callbacks on a
            # worker thread so a callback may safely re-enter the connector
            # (read/write) without deadlocking the loop, and wait for them to
            # finish so delivery is observable to the caller.
            executor = self._ensure_callback_executor()
            future = executor.submit(
                self._run_subscriptions, subscriptions, payload, other, True
            )
            future.result()
        else:
            self._run_subscriptions(subscriptions, payload, other, False)

    def _run_subscriptions(
        self,
        subscriptions: list[_MqttSubscription],
        payload: bytes,
        other: MqttSubscriptionArguments,
        reentrant: bool,
    ) -> None:
        """Decode per subscriber and invoke each callback."""
        if reentrant:
            self._set_reentrant_dispatch(True)
        try:
            for sub in subscriptions:
                try:
                    value = self.deserialize_value(payload, sub.resource)
                except Exception as exp:
                    _logger.error(
                        "Failed to deserialize MQTT payload for topic "
                        f"'{sub.topic}'"
                    )
                    _logger.error(exp)
                    continue
                try:
                    sub.callback(value, other)
                except Exception as exp:
                    _logger.error(
                        "MQTT subscription callback for topic "
                        f"'{sub.topic}' failed"
                    )
                    _logger.error(exp)
        finally:
            if reentrant:
                self._set_reentrant_dispatch(False)

    def _ensure_callback_executor(self) -> ThreadPoolExecutor:
        """Return the single-worker executor used to dispatch callbacks."""
        if self._callback_executor is None:
            self._callback_executor = ThreadPoolExecutor(
                max_workers=1,
                thread_name_prefix=f"mqtt-callbacks-{self.name}",
            )
        return self._callback_executor

    def _shutdown_callback_executor(self) -> None:
        """Tear down the callback dispatch executor, if it was created."""
        if self._callback_executor is not None:
            self._callback_executor.shutdown(wait=False)
            self._callback_executor = None

    def _message_topic(self, message: Any) -> str:
        """Extract the topic string from an aiomqtt message."""
        message_topic = message.topic
        topic = getattr(message_topic, "value", None)
        if topic is None:
            topic = str(message_topic)
        return validate_topic(topic)

    @staticmethod
    def _message_payload(message: Any) -> bytes:
        """Extract message payload without copying existing bytes."""
        payload = message.payload
        if isinstance(payload, bytes):
            return payload
        return bytes(payload)

    def serialize_value(
        self,
        value: Any,
        resource: RemoteResource,
    ) -> bytes:
        """Serialize a value using this connector's configured payload codec."""
        return normalize_mqtt_payload(
            self._payload_serializer(
                value,
                resource,
            )
        )

    def deserialize_value(
        self,
        payload: bytes | bytearray,
        resource: RemoteResource,
    ) -> Any:
        """Deserialize a payload using this connector's configured codec."""
        return self._payload_deserializer(
            payload,
            resource,
        )

    @property
    def payload_codec(self) -> str:
        """Return the configured built-in payload codec name."""
        return self._payload_codec

    @payload_codec.setter
    def payload_codec(self, codec: str | MqttPayloadCodec) -> None:
        """Configure built-in MQTT payload serialization."""
        payload_codec = get_mqtt_payload_codec(codec)
        self._payload_codec = payload_codec.name
        self._payload_serializer = payload_codec.serializer
        self._payload_deserializer = payload_codec.deserializer

    @property
    def payload_serializer(self) -> MqttPayloadSerializer:
        """Return the active MQTT payload serializer."""
        return self._payload_serializer

    @payload_serializer.setter
    def payload_serializer(self, serializer: MqttPayloadSerializer) -> None:
        """Override the active MQTT payload serializer."""
        if not callable(serializer):
            raise TypeError("MQTT payload_serializer must be callable")
        self._payload_serializer = serializer

    @property
    def payload_deserializer(self) -> MqttPayloadDeserializer:
        """Return the active MQTT payload deserializer."""
        return self._payload_deserializer

    @payload_deserializer.setter
    def payload_deserializer(
        self,
        deserializer: MqttPayloadDeserializer,
    ) -> None:
        """Override the active MQTT payload deserializer."""
        if not callable(deserializer):
            raise TypeError("MQTT payload_deserializer must be callable")
        self._payload_deserializer = deserializer

    def _resolve_subscribe_topic(
        self,
        resource: RemoteResource,
    ) -> str:
        """Resolve the topic used for reads and subscriptions."""
        path = resource.path
        remote_resource_spec = self._mqtt_spec(resource)
        if remote_resource_spec is None:
            return validate_topic(join_topic(self.topic_prefix, path))
        return remote_resource_spec.resolve_subscribe_topic(
            path=path,
            default_topic_prefix=self.topic_prefix,
        )

    def _resolve_publish_topic(
        self,
        resource: RemoteResource,
    ) -> str:
        """Resolve the topic used for writes."""
        path = resource.path
        remote_resource_spec = self._mqtt_spec(resource)
        if remote_resource_spec is None:
            return validate_topic(join_topic(self.topic_prefix, path))
        return remote_resource_spec.resolve_publish_topic(
            path=path,
            default_topic_prefix=self.topic_prefix,
        )

    def _mqtt_spec(
        self,
        resource: RemoteResource,
    ) -> MqttRemoteResourceSpec | None:
        """Return the MQTT spec or fail when another protocol is supplied."""
        if resource.spec is None:
            return None
        if not isinstance(resource.spec, MqttRemoteResourceSpec):
            raise TypeError(
                "resource.spec must be an MqttRemoteResourceSpec or None"
            )
        return resource.spec

    def _resolve_qos(self, resource: RemoteResource) -> int:
        """Resolve the QoS for a node operation."""
        remote_resource_spec = self._mqtt_spec(resource)
        if (
            remote_resource_spec is not None
            and remote_resource_spec.qos is not None
        ):
            return remote_resource_spec.qos
        return self.qos

    def _resolve_retain(self, resource: RemoteResource) -> bool:
        """Resolve the retain flag for a node publish."""
        remote_resource_spec = self._mqtt_spec(resource)
        if (
            remote_resource_spec is not None
            and remote_resource_spec.retain is not None
        ):
            return remote_resource_spec.retain
        return self.retain

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation.

        Environment-variable references are preserved instead of their resolved
        values so that a dump/reload stays env-driven.
        """
        data: dict[str, Any] = {
            "name": self.name,
            "id": self.id,
        }
        data.update(self.address_to_dict())
        data.update(self.auth_to_dict())
        data.update(
            {
                "client_id": self.client_id,
                "topic_prefix": self.topic_prefix,
                "keepalive": self.keepalive,
                "qos": self.qos,
                "retain": self.retain,
                "payload_codec": self.payload_codec,
            }
        )
        return data

    def __str__(self) -> str:  # pyrefly: ignore[missing-override-decorator]
        return (
            "MqttConnector("
            f"name={self.name!r}, "
            f"id={self.id!r}, "
            f"ip={self.ip!r}, "
            f"port={self.port!r}, "
            f"client_id={self.client_id!r}, "
            f"topic_prefix={self.topic_prefix!r}, "
            f"keepalive={self.keepalive!r}, "
            f"qos={self.qos!r}, "
            f"retain={self.retain!r}, "
            f"payload_codec={self.payload_codec!r}"
            ")"
        )

    def __repr__(self) -> str:  # pyrefly: ignore[missing-override-decorator]
        return self.__str__()
