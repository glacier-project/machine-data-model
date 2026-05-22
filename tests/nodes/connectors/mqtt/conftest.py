import asyncio
from collections.abc import Generator
from pathlib import Path
import time
from typing import Any, cast

import aiomqtt
import docker
from docker.models.containers import Container
import pytest

# Total budget for the broker to come up. Polled with exponential backoff
# (start at 50 ms, double up to 2 s) so cold container starts are tolerated
# without wasting cycles when the broker is already ready.
MQTT_READINESS_TIMEOUT_S = 30.0
MQTT_INITIAL_BACKOFF_S = 0.05
MQTT_MAX_BACKOFF_S = 2.0


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
    ports = cast(dict[str, Any], container.ports)
    container_host_port = ports[container_guest_port][0]["HostPort"]
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
    """Block until the broker accepts an MQTT connect, with backoff.

    Polls with exponential backoff (capped at MQTT_MAX_BACKOFF_S) inside a
    MQTT_READINESS_TIMEOUT_S budget. Bails immediately if the container
    exits, since further retries would never succeed.
    """
    deadline = time.monotonic() + MQTT_READINESS_TIMEOUT_S
    backoff = MQTT_INITIAL_BACKOFF_S
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        container.reload()
        if container.status == "exited":
            raise RuntimeError("MQTT test broker container exited unexpectedly")
        try:
            asyncio.run(_check_broker_connection(port))
            return
        except Exception as exc:
            last_error = exc
            time.sleep(backoff)
            backoff = min(backoff * 2, MQTT_MAX_BACKOFF_S)
    raise TimeoutError(
        f"MQTT test broker did not become ready within "
        f"{MQTT_READINESS_TIMEOUT_S}s; last error: {last_error}"
    )


async def _check_broker_connection(port: int) -> None:
    async with aiomqtt.Client(hostname="127.0.0.1", port=port):
        pass
