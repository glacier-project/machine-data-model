import time

import pytest

from typing import Tuple, Any, Generator
import docker
from docker.models.containers import Container


@pytest.fixture(scope="module")
def start_opcua_test_server() -> Generator[Tuple[Container, int], Any, None]:
    docker_client = docker.from_env()
    container_guest_port = "50000/tcp"
    container = docker_client.containers.run(
        "mcr.microsoft.com/iotedge/opc-plc@sha256:1fda0e687dee9bd86e1d40ad3e1e4a81d087777d59cab5abd62fdba9c3eefa9e",
        "--pn=50000 --autoaccept --sph --sn=5 --sr=10 --st=uint --fn=5 --fr=1 --ft=uint --gn=5",
        auto_remove=True,
        remove=True,
        detach=True,
        ports={container_guest_port: None},  # None: random host port
    )

    # retrieve randomly generated port
    container.reload()
    container_host_port = container.ports.get(container_guest_port)[0]["HostPort"]
    assert str.isnumeric(container_host_port), "container_host_port must be numeric"
    container_host_port = int(container_host_port)

    while docker_client.containers.get(container.id).status != "running":
        time.sleep(0.5)

    while "PLC simulation started, press Ctrl+C to exit" not in str(container.logs()):
        time.sleep(0.5)

    yield container, container_host_port

    # teardown
    container.stop()
    return None
