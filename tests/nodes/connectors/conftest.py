import asyncio
import time
import os
from pathlib import Path

import pytest

from typing import Tuple, Any, Generator
import docker
from docker.models.containers import Container
from asyncua.client.client import Client
from asyncua.crypto.security_policies import SecurityPolicyBasic256Sha256
from cryptography.x509.oid import ExtendedKeyUsageOID
from asyncua.crypto.cert_gen import setup_self_signed_certificate


@pytest.fixture(scope="session")
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

    while container.status != "running":
        time.sleep(0.5)
        container.reload()

    async def check_opcua_connection():
        # Setup self-signed certificate for the client
        cert_dir = Path("tests/certificates/opcua")
        cert_dir.mkdir(parents=True, exist_ok=True)

        private_key_path = cert_dir / "private.selfsigned.pem"
        certificate_path = cert_dir / "cert.selfsigned.der"

        # Always generate fresh certificates for tests
        await setup_self_signed_certificate(
            private_key_path,
            certificate_path,
            f"urn:test-machine-data-model-client",
            "test-machine-data-model-client",
            [ExtendedKeyUsageOID.CLIENT_AUTH],
            {
                "countryName": "CN",
                "stateOrProvinceName": "AState",
                "localityName": "Foo",
                "organizationName": "Bar Ltd",
            },
        )

        client = Client(f"opc.tcp://localhost:{container_host_port}")

        connected = False
        while not connected:
            try:
                await client.set_security(
                    SecurityPolicyBasic256Sha256,
                    certificate=str(certificate_path),
                    private_key=str(private_key_path),
                    server_certificate=None,
                )
                connected = True
            except:
                pass
            await asyncio.sleep(0.1)
        await client.disconnect()

    asyncio.run(check_opcua_connection())
    # time.sleep(2)  # wait for server to be ready

    try:
        yield container, container_host_port
    finally:
        # teardown
        container.stop()

    return None
