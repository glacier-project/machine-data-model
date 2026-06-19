import asyncio
from collections.abc import Generator
from contextlib import suppress
from pathlib import Path
import time
from typing import Any

from asyncua.client.client import Client
from asyncua.crypto.cert_gen import setup_self_signed_certificate
from asyncua.crypto.security_policies import SecurityPolicyBasic256Sha256
from asyncua.crypto.validator import (
    CertificateValidator,
    CertificateValidatorOptions,
)
from asyncua.sync import Server
from cryptography.x509.oid import ExtendedKeyUsageOID
import docker
from docker.models.containers import Container
import pytest

from tests.nodes.connectors.opcua import create_server

OPCUA_CLIENT_APP_URI = "urn:test-machine-data-model-client"
OPCUA_CLIENT_HOSTNAME = "test-machine-data-model-client"
OPCUA_MAX_ATTEMPTS = 50
OPCUA_CONNECTION_RETRY_DELAY = 0.1
OPCUA_CONTAINER_RETRY_DELAY = 0.5


@pytest.fixture(scope="session")
def start_opcua_test_server() -> Generator[tuple[Container, int], Any, None]:
    docker_client = docker.from_env()
    container_guest_port = "50000/tcp"
    container = docker_client.containers.run(
        "mcr.microsoft.com/iotedge/opc-plc:latest",
        "--pn=50000 --autoaccept --sph --sn=5 --sr=10 --st=uint "
        "--fn=5 --fr=1 --ft=uint --gn=5",
        auto_remove=True,
        remove=True,
        detach=True,
        # None: random host port
        ports={container_guest_port: None},
    )

    # retrieve randomly generated port
    container.reload()
    container_host_port = container.ports.get(container_guest_port)[0][
        "HostPort"
    ]
    assert str.isnumeric(
        container_host_port
    ), "container_host_port must be numeric"
    container_host_port = int(container_host_port)

    attempts = 0
    while attempts < OPCUA_MAX_ATTEMPTS and container.status != "running":
        attempts += 1
        time.sleep(OPCUA_CONTAINER_RETRY_DELAY)
        container.reload()
        # if the container has exited, raise an error
        if container.status == "exited":
            raise RuntimeError(
                "OPC UA test server container exited unexpectedly."
            )
    if container.status != "running":
        raise TimeoutError("OPC UA test server container did not start")

    async def check_opcua_connection() -> None:
        private_key_path, certificate_path = await _setup_opcua_certificate()
        await _wait_for_opcua_connection(
            container_host_port,
            private_key_path=private_key_path,
            certificate_path=certificate_path,
        )

    asyncio.run(check_opcua_connection())
    # time.sleep(2)  # wait for server to be ready

    try:
        yield container, container_host_port
    finally:
        # teardown
        container.stop()

    return None


@pytest.fixture(scope="session")
def start_custom_opcua_server() -> Generator[tuple[Server, int], Any, None]:
    server, port = create_server()

    async def check_opcua_connection() -> None:
        await _setup_opcua_certificate()
        await _wait_for_opcua_connection(port)

    asyncio.run(check_opcua_connection())

    try:
        yield server, port
    finally:
        server.stop()
    return None


async def _setup_opcua_certificate() -> tuple[Path, Path]:
    # Setup self-signed certificate for the client
    cert_dir = Path("tests/certificates/opcua")
    cert_dir.mkdir(parents=True, exist_ok=True)

    private_key_path = cert_dir / "private.selfsigned.pem"
    certificate_path = cert_dir / "cert.selfsigned.der"

    # Always generate fresh certificates for tests
    await setup_self_signed_certificate(
        private_key_path,
        certificate_path,
        OPCUA_CLIENT_APP_URI,
        OPCUA_CLIENT_HOSTNAME,
        [ExtendedKeyUsageOID.CLIENT_AUTH],
        {
            "countryName": "CN",
            "stateOrProvinceName": "AState",
            "localityName": "Foo",
            "organizationName": "Bar Ltd",
        },
    )
    return private_key_path, certificate_path


async def _wait_for_opcua_connection(
    port: int,
    *,
    private_key_path: Path | None = None,
    certificate_path: Path | None = None,
) -> None:
    for _ in range(OPCUA_MAX_ATTEMPTS):
        client = Client(f"opc.tcp://localhost:{port}")
        client.application_uri = OPCUA_CLIENT_APP_URI
        try:
            if private_key_path is not None and certificate_path is not None:
                await client.set_security(
                    SecurityPolicyBasic256Sha256,
                    certificate=str(certificate_path),
                    private_key=str(private_key_path),
                    server_certificate=None,
                )
                client.certificate_validator = CertificateValidator(
                    CertificateValidatorOptions.EXT_VALIDATION
                    | CertificateValidatorOptions.PEER_SERVER
                )
            await client.connect()
            return
        except Exception:
            await asyncio.sleep(OPCUA_CONNECTION_RETRY_DELAY)
        finally:
            with suppress(Exception):
                await client.disconnect()
    raise TimeoutError("OPC UA test server did not become ready")
