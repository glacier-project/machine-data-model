"""This script uses asyncua directly to interact with the server."""

import asyncio
from asyncio import AbstractEventLoop
import logging
from pathlib import Path
import socket
import sys
from typing import Any

from cryptography.x509.oid import ExtendedKeyUsageOID

sys.path.insert(0, "..")
from asyncua import Client, ua
from asyncua.common.node import Node
from asyncua.common.subscription import (
    DataChangeNotif,
    DataChangeNotificationHandler,
)
from asyncua.crypto.cert_gen import setup_self_signed_certificate
from asyncua.crypto.security_policies import SecurityPolicyBasic256Sha256
from asyncua.crypto.truststore import TrustStore
from asyncua.crypto.validator import (
    CertificateValidator,
    CertificateValidatorOptions,
)

logging.basicConfig(level=logging.WARNING)
_logger = logging.getLogger(__name__)

USE_TRUST_STORE = False

cert_idx = 4
cert_base = Path(__file__).parent
cert = Path(cert_base / f"certificates/peer-certificate-example-{cert_idx}.der")
private_key = Path(
    cert_base / f"certificates/peer-private-key-example-{cert_idx}.pem"
)


class TempChangeHandler(DataChangeNotificationHandler):
    """Handler for temperature change notifications."""

    def datachange_notification(
        self, node: Node, val: Any, data: DataChangeNotif
    ) -> None:
        """Called for every datachange notification from server."""
        print("detected val change:", val)


async def turn_heater_off(objects: Node) -> None:
    """Turn the heater off."""
    methods = await objects.get_child("3:OpcPlc/3:Methods")
    await methods.call_method("4:HeaterOff")


async def turn_heater_on(objects: Node) -> None:
    """Turn the heater on."""
    methods = await objects.get_child("3:OpcPlc/3:Methods")
    await methods.call_method("4:HeaterOn")


async def setup_temp_change_handler(client: Client, objects: Node) -> None:
    """Setup temperature change handler and subscription."""
    temp_subscription = await client.create_subscription(1, TempChangeHandler())
    temp = await objects.get_child(
        "4:Boilers/4:Boiler #2/2:ParameterSet/4:CurrentTemperature"
    )
    await temp_subscription.subscribe_data_change(temp)


async def task(_loop: AbstractEventLoop) -> None:
    """Main async task for the asyncua client example."""
    host_name = socket.gethostname()
    client_app_uri = f"urn:{host_name}:foobar:myselfsignedclient"
    url = "opc.tcp://localhost:50000"

    await setup_self_signed_certificate(
        private_key,
        cert,
        client_app_uri,
        host_name,
        [ExtendedKeyUsageOID.CLIENT_AUTH],
        {
            "countryName": "CN",
            "stateOrProvinceName": "AState",
            "localityName": "Foo",
            "organizationName": "Bar Ltd",
        },
    )
    client = Client(url=url)
    client.application_uri = client_app_uri
    await client.set_security(
        SecurityPolicyBasic256Sha256,
        certificate=str(cert),
        private_key=str(private_key),
        server_certificate=None,  # "certificate-example.der",
    )

    if USE_TRUST_STORE:
        trust_store = TrustStore(
            [Path("examples") / "certificates" / "trusted" / "certs"], []
        )
        await trust_store.load()
        validator = CertificateValidator(
            CertificateValidatorOptions.TRUSTED_VALIDATION
            | CertificateValidatorOptions.PEER_SERVER,
            trust_store,
        )
    else:
        validator = CertificateValidator(
            CertificateValidatorOptions.EXT_VALIDATION
            | CertificateValidatorOptions.PEER_SERVER
        )
    client.certificate_validator = validator

    try:
        async with client:
            objects: Node = client.nodes.objects
            await setup_temp_change_handler(client, objects)

            asset_id = await objects.get_child(
                "4:Boilers/4:Boiler #2/2:AssetId"
            )
            print("AssetId value:", await asset_id.get_value())

            print("Turning off the heater...")
            await turn_heater_off(objects)

            temp = await objects.get_child(
                "4:Boilers/4:Boiler #2/2:ParameterSet/4:CurrentTemperature"
            )
            print("CurrentTemperature value:", await temp.get_value())
            await asyncio.sleep(5)

            print("Turning on the heater...")
            await turn_heater_on(objects)

            reference_methods = await objects.get_child(
                "6:ReferenceTest/6:Methods"
            )
            a = ua.Variant(2, ua.VariantType.Float)
            b = ua.Variant(5, ua.VariantType.UInt32)
            res = await reference_methods.call_method("6:Methods_Add", a, b)
            print("Adding 2 + 5: result is", res)

            await asyncio.sleep(10)
    except ua.UaError as exp:
        _logger.error(exp)


def main() -> None:
    """Main entry point for the asyncua client example."""
    loop = asyncio.new_event_loop()
    loop.set_debug(True)
    loop.run_until_complete(task(loop))
    loop.close()


if __name__ == "__main__":
    main()
