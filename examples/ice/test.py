import os
import asyncio
import logging
import asyncua
from asyncua.ua import Variant, VariantType

ip = os.getenv("ICE_CONVEYOR_IP")
port = os.getenv("ICE_CONVEYOR_PORT")
node_id = "ns=7;g=0c3140a2-b72c-c4a8-cc1a-f6787c6f8ae5"
method_id = "ns=7;g=25ddc5dc-e471-ab51-b57d-f0845f33f662"
url = f"opc.tcp://{ip}:{port}"


async def main():
    async with asyncua.Client(url=url) as client:
        node = client.get_node(node_id)
        print(f"{node=}")
        method = client.get_node(method_id)
        print(f"{method=}")
        methods = await node.get_methods()
        print(f"{methods=}")
        parent = await method.get_parent()
        res = parent.call_method(method, Variant(1, VariantType.Byte), Variant(1, VariantType.Byte))
        print(f"{res=}")
        res = await res
        print(f"{res=}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(main(), debug=True)
