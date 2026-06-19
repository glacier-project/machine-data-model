from typing import TYPE_CHECKING, Any

from typing_extensions import override

from machine_data_model.nodes.connectors.abstract_remote_resource_spec import (
    AbstractRemoteResourceSpec,
)

if TYPE_CHECKING:
    from machine_data_model.nodes.data_model_node import DataModelNode


def _normalize_topic(topic: str) -> str:
    """Normalize a configured MQTT topic without changing inner segments."""
    return topic.strip("/")


def _join_topic(prefix: str | None, topic: str | None) -> str:
    """Join a topic prefix and a relative topic."""
    parts = []
    if prefix is not None and prefix.strip("/"):
        parts.append(prefix.strip("/"))
    if topic is not None and topic.strip("/"):
        parts.append(topic.strip("/"))
    return "/".join(parts)


def _validate_topic(topic: str) -> str:
    """Validate first-pass MQTT topic support."""
    topic = _normalize_topic(topic)
    if not topic:
        raise ValueError("MQTT topic cannot be empty")
    if "+" in topic or "#" in topic:
        raise ValueError("MQTT topic wildcards are not supported")
    return topic


class MqttRemoteResourceSpec(AbstractRemoteResourceSpec):
    """Represents node properties that are specific for MQTT."""

    def __init__(
        self,
        remote_path: str | None = None,
        topic: str | None = None,
        topic_prefix: str | None = None,
        publish_topic: str | None = None,
        subscribe_topic: str | None = None,
        qos: int | None = None,
        retain: bool | None = None,
    ) -> None:
        """Constructor.

        Args:
            remote_path (str | None):
                Compatibility alias for an explicit MQTT topic.
            topic (str | None):
                Explicit read/write topic.
            topic_prefix (str | None):
                Inheritable prefix used for derived topics.
            publish_topic (str | None):
                Explicit write topic.
            subscribe_topic (str | None):
                Explicit read/subscription topic.
            qos (int | None):
                Per-node QoS override.
            retain (bool | None):
                Per-node retain override.
        """
        super().__init__(remote_path=remote_path)
        if qos is not None and qos not in (0, 1, 2):
            raise ValueError("MQTT QoS must be 0, 1, or 2")
        if retain is not None and not isinstance(retain, bool):
            raise TypeError("MQTT retain must be a bool or None")
        self.topic = topic
        self.topic_prefix = topic_prefix
        self.publish_topic = publish_topic
        self.subscribe_topic = subscribe_topic
        self.qos = qos
        self.retain = retain

    @override
    def get_remote_path(
        self,
        node: "DataModelNode | None" = None,
    ) -> str | None:
        """Return the explicit or locally derivable MQTT subscription topic."""
        if self.has_explicit_subscribe_topic():
            return self.resolve_subscribe_topic()
        if self.topic_prefix and node is not None:
            return self.resolve_subscribe_topic(path=node.qualified_name)
        return None

    def has_explicit_subscribe_topic(self) -> bool:
        """Return whether reads/subscriptions have an explicit topic."""
        return (
            self.subscribe_topic is not None
            or self.topic is not None
            or self.remote_path is not None
        )

    def resolve_subscribe_topic(
        self,
        path: str | None = None,
        default_topic_prefix: str | None = None,
    ) -> str:
        """Resolve the MQTT topic used for reads and subscriptions."""
        explicit_topic = self._first_configured_topic(
            self.subscribe_topic,
            self.topic,
            self.remote_path,
        )
        if explicit_topic is not None:
            return _validate_topic(explicit_topic)
        return self._derive_topic(path, default_topic_prefix)

    def resolve_publish_topic(
        self,
        path: str | None = None,
        default_topic_prefix: str | None = None,
    ) -> str:
        """Resolve the MQTT topic used for writes."""
        if self.publish_topic is not None:
            return _validate_topic(self.publish_topic)
        return self.resolve_subscribe_topic(path, default_topic_prefix)

    def _derive_topic(
        self,
        path: str | None,
        default_topic_prefix: str | None,
    ) -> str:
        """Derive a topic from the node qualified name or provided path."""
        derived_path = path
        topic = _join_topic(
            self.topic_prefix
            if self.topic_prefix is not None
            else default_topic_prefix,
            derived_path,
        )
        return _validate_topic(topic)

    @staticmethod
    def _first_configured_topic(*topics: str | None) -> str | None:
        """Return the first configured topic, preserving empty strings."""
        for topic in topics:
            if topic is not None:
                return topic
        return None

    @override
    def inheritable_spec(self) -> "MqttRemoteResourceSpec":
        """Returns the inheritable part of this object."""
        return MqttRemoteResourceSpec(topic_prefix=self.topic_prefix)

    @override
    def clone_for_child(self) -> "MqttRemoteResourceSpec":
        """Create an MQTT spec for a child node."""
        return MqttRemoteResourceSpec(
            topic_prefix=self.topic_prefix,
        )

    @override
    def inherit_spec(self, parent: AbstractRemoteResourceSpec) -> None:
        """Inherits MQTT topic prefix from another spec."""
        if not isinstance(parent, MqttRemoteResourceSpec):
            return
        if self.topic_prefix is None:
            self.topic_prefix = parent.topic_prefix

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "remote_path": self.remote_path,
            "topic": self.topic,
            "topic_prefix": self.topic_prefix,
            "publish_topic": self.publish_topic,
            "subscribe_topic": self.subscribe_topic,
            "qos": self.qos,
            "retain": self.retain,
        }

    def __str__(self) -> str:
        return (
            "MqttRemoteResourceSpec("
            f"remote_path={self.remote_path!r}, "
            f"topic={self.topic!r}, "
            f"topic_prefix={self.topic_prefix!r}, "
            f"publish_topic={self.publish_topic!r}, "
            f"subscribe_topic={self.subscribe_topic!r}, "
            f"qos={self.qos!r}, "
            f"retain={self.retain!r}"
            ")"
        )

    def __repr__(self) -> str:
        return self.__str__()
