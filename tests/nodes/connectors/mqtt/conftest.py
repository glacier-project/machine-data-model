import asyncio
from collections.abc import Generator
from pathlib import Path
import time
from typing import Any

import aiomqtt
import docker
from docker.models.containers import Container
import pytest

MQTT_MAX_ATTEMPTS = 50
MQTT_CONNECTION_RETRY_DELAY = 0.1


@pytest.fixture(scope="session")
def start_mqtt_test_broker(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[tuple[Container, int], Any, None]:
    docker_client = docker.from_env()
    config_path = _write_mosquitto_config(
        tmp_path_factory.mktemp("mqtt_broker")
    )
    container_guest_port = "1883/tcp"
    container = docker_client.containers.run(
        "eclipse-mosquitto:2",
        detach=True,
        auto_remove=True,
        remove=True,
        ports={container_guest_port: None},
        volumes={
            str(config_path): {
                "bind": "/mosquitto/config/mosquitto.conf",
                "mode": "ro",
            }
        },
    )

    container.reload()
    # pyrefly: ignore[unsupported-operation]
    container_host_port = container.ports.get(container_guest_port)[0][
        "HostPort"
    ]
    assert str.isnumeric(container_host_port)
    container_host_port = int(container_host_port)

    try:
        _wait_for_broker(container, container_host_port)
        yield container, container_host_port
    finally:
        container.stop()


def _write_mosquitto_config(config_dir: Path) -> Path:
    config_path = config_dir / "mosquitto.conf"
    config_path.write_text(
        "listener 1883 0.0.0.0\n" "allow_anonymous true\n" "persistence false\n"
    )
    return config_path


def _wait_for_broker(container: Container, port: int) -> None:
    attempts = 0
    while attempts < MQTT_MAX_ATTEMPTS:
        attempts += 1
        container.reload()
        if container.status == "exited":
            raise RuntimeError("MQTT test broker container exited unexpectedly")
        try:
            asyncio.run(_check_broker_connection(port))
            return
        except Exception:
            time.sleep(MQTT_CONNECTION_RETRY_DELAY)
    raise TimeoutError("MQTT test broker did not become ready")


async def _check_broker_connection(port: int) -> None:
    async with aiomqtt.Client(hostname="127.0.0.1", port=port):
        pass
