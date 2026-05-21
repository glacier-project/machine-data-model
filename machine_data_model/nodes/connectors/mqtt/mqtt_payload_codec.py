"""Pluggable payload codecs for the MQTT connector.

Encodes and decodes the byte payloads exchanged with an MQTT broker. The
codec is selected per-connector (or per-resource) by name and resolves to a
serializer / deserializer pair.
"""

from collections.abc import Callable
from dataclasses import dataclass
import json
import re
from typing import Any, Final, cast

import msgpack

from machine_data_model.nodes.connectors.remote_resource import RemoteResource
from machine_data_model.nodes.variable_node import (
    BooleanVariableNode,
    NumericalVariableNode,
    StringVariableNode,
)

MqttSerializedPayload = bytes | bytearray | str
MqttPayloadSerializer = Callable[[Any, RemoteResource], MqttSerializedPayload]
MqttPayloadDeserializer = Callable[[bytes | bytearray, RemoteResource], Any]

_INT_LITERAL: Final = re.compile(r"^[+-]?\d+$")
_FLOAT_LITERAL: Final = re.compile(
    r"^[+-]?(?:(?:\d+\.\d*)|(?:\.\d+)|(?:\d+))(?:[eE][+-]?\d+)?$"
)
_JSON_ENCODE: Final = json.JSONEncoder(
    ensure_ascii=False,
    separators=(",", ":"),
).encode
_JSON_LOADS: Final = json.loads
_MSGPACK_PACKB: Final = msgpack.packb
_MSGPACK_UNPACKB: Final = msgpack.unpackb


@dataclass(frozen=True)
class MqttPayloadCodec:
    """Serialize and deserialize MQTT payloads."""

    name: str
    serializer: MqttPayloadSerializer
    deserializer: MqttPayloadDeserializer

    def serialize(
        self,
        value: Any,
        resource: RemoteResource,
    ) -> MqttSerializedPayload:
        """Serialize a value into an MQTT payload."""
        return self.serializer(value, resource)

    def deserialize(
        self,
        payload: bytes | bytearray,
        resource: RemoteResource,
    ) -> Any:
        """Deserialize an MQTT payload into a Python value."""
        return self.deserializer(payload, resource)


def normalize_mqtt_payload(payload: MqttSerializedPayload) -> bytes:
    """Normalize serializer output to bytes for MQTT publish calls."""
    if isinstance(payload, bytes):
        return payload
    if isinstance(payload, bytearray):
        return bytes(payload)
    if isinstance(payload, str):
        return payload.encode("utf-8")
    raise TypeError("MQTT payload serializers must return bytes or str")


def serialize_mqtt_value(
    value: Any,
    resource: RemoteResource,
    codec: str | MqttPayloadCodec = "string",
) -> bytes:
    """Serialize a value with one of the configured MQTT payload codecs."""
    payload_codec = get_mqtt_payload_codec(codec)
    return normalize_mqtt_payload(
        payload_codec.serialize(
            value,
            resource,
        )
    )


def deserialize_mqtt_value(
    payload: bytes | bytearray,
    resource: RemoteResource,
    codec: str | MqttPayloadCodec = "string",
) -> Any:
    """Deserialize a value with one of the configured MQTT payload codecs."""
    payload_codec = get_mqtt_payload_codec(codec)
    return payload_codec.deserialize(
        payload,
        resource,
    )


def serialize_string_payload(value: Any, _resource: RemoteResource) -> bytes:
    """Encode supported scalar values as UTF-8 MQTT payloads."""
    if isinstance(value, bool):
        return b"true" if value else b"false"
    if isinstance(value, str):
        return value.encode("utf-8")
    if isinstance(value, int | float):
        return str(value).encode("utf-8")
    raise TypeError(
        "MQTT string payloads currently support only str, int, float, and bool"
    )


def deserialize_string_payload(
    payload: bytes | bytearray, resource: RemoteResource
) -> Any:
    """Decode supported scalar values from UTF-8 MQTT payloads."""
    value = payload.decode("utf-8")
    node_type = resource.node_type
    if node_type is None:
        return _infer_scalar_value(value)
    if issubclass(node_type, StringVariableNode):
        return value
    if issubclass(node_type, BooleanVariableNode):
        return _decode_bool(value)
    if issubclass(node_type, NumericalVariableNode):
        return _decode_number(value)
    return _infer_scalar_value(value)


def _infer_scalar_value(value: str) -> Any:
    """Infer bool, int, float, or str from a decoded scalar string."""
    stripped_value = value.strip()
    lower_value = stripped_value.lower()
    if lower_value == "true":
        return True
    if lower_value == "false":
        return False
    if _INT_LITERAL.fullmatch(stripped_value):
        return int(stripped_value)
    if _FLOAT_LITERAL.fullmatch(stripped_value):
        return float(stripped_value)
    return value


def _decode_bool(value: str) -> bool:
    """Decode a boolean string."""
    lower_value = value.strip().lower()
    if lower_value == "true":
        return True
    if lower_value == "false":
        return False
    raise ValueError(f"Cannot decode MQTT payload {value!r} as a bool")


def _decode_number(value: str) -> int | float:
    """Decode an integer or floating point string."""
    stripped_value = value.strip()
    if _INT_LITERAL.fullmatch(stripped_value):
        return int(stripped_value)
    if _FLOAT_LITERAL.fullmatch(stripped_value):
        return float(stripped_value)
    raise ValueError(f"Cannot decode MQTT payload {value!r} as a number")


def serialize_json_payload(value: Any, _resource: RemoteResource) -> bytes:
    """Encode a value as compact UTF-8 JSON."""
    return _JSON_ENCODE(value).encode("utf-8")


def deserialize_json_payload(
    payload: bytes | bytearray, _resource: RemoteResource
) -> Any:
    """Decode a JSON payload."""
    return _JSON_LOADS(payload)


def serialize_msgpack_payload(value: Any, _resource: RemoteResource) -> bytes:
    """Encode a value as MessagePack."""
    return cast(bytes, _MSGPACK_PACKB(value, use_bin_type=True))


def deserialize_msgpack_payload(
    payload: bytes | bytearray, _resource: RemoteResource
) -> Any:
    """Decode a MessagePack payload."""
    return _MSGPACK_UNPACKB(payload, raw=False)


STRING_MQTT_PAYLOAD_CODEC: Final = MqttPayloadCodec(
    name="string",
    serializer=serialize_string_payload,
    deserializer=deserialize_string_payload,
)
JSON_MQTT_PAYLOAD_CODEC: Final = MqttPayloadCodec(
    name="json",
    serializer=serialize_json_payload,
    deserializer=deserialize_json_payload,
)
MSGPACK_MQTT_PAYLOAD_CODEC: Final = MqttPayloadCodec(
    name="msgpack",
    serializer=serialize_msgpack_payload,
    deserializer=deserialize_msgpack_payload,
)
_BUILTIN_PAYLOAD_CODECS: Final = {
    "string": STRING_MQTT_PAYLOAD_CODEC,
    "str": STRING_MQTT_PAYLOAD_CODEC,
    "scalar": STRING_MQTT_PAYLOAD_CODEC,
    "json": JSON_MQTT_PAYLOAD_CODEC,
    "msgpack": MSGPACK_MQTT_PAYLOAD_CODEC,
    "messagepack": MSGPACK_MQTT_PAYLOAD_CODEC,
}


def get_mqtt_payload_codec(codec: str | MqttPayloadCodec) -> MqttPayloadCodec:
    """Return a configured MQTT payload codec."""
    if isinstance(codec, MqttPayloadCodec):
        return codec
    codec_name = codec.strip().lower()
    if codec_name in _BUILTIN_PAYLOAD_CODECS:
        return _BUILTIN_PAYLOAD_CODECS[codec_name]
    raise ValueError(
        "Unsupported MQTT payload codec. Expected 'string', 'json', or "
        "'msgpack'."
    )
