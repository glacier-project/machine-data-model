# OPCUA EXAMPLE

This example uses the machine-data-model library to connect to an OPCUA server.

## Prerequisites

- Install the machine-data-model library
- Download the example certificates from the asyncua repository, examples folder: https://github.com/FreeOpcUa/opcua-asyncio
- Run the following OPCUA sample server using docker: https://github.com/Azure-Samples/iot-edge-opc-plc

## How to run the example

Launch the `connect.py` file using python.

`connect.py` will use the `opcua.yml` file to connect to the OPCUA server.
