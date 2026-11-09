# Machine Data Model

This library simplifies the creation of machine data models in the manufacturing
domain. It provides a structured and efficient way to represent machine data,
enabling seamless integration with various protocols and systems.
The library is designed to be extensible, allowing users to define their own data
models and integrate them with existing systems.
This library is inspired by standards such as the OPC UA information model, ISA-95 data model,
RAMI 4.0, SoM-like data models, and others.

## Nodes

The data model is organized in a tree-like structure, where each node
represents one of the following:

- **Folder**: a folder that can contain other folders or variables;
- **Variable**: a variable storing a simple data type (i.e., string, numeric,
  boolean) or a complex data type (i.e., object);
- **Method**: a method that represents an action that can be invoked on request.

Each node has the following attributes:

- **Id**: a unique identifier for the node;
- **Name**: a human-readable name for the node;
- **Description**: a description of the node;
- **Parent**: the parent node;

### Folder Nodes

Folder nodes are used to organize the data model into a hierarchical structure.
They can contain other folder nodes or variable nodes.
The root node of the data model is always a folder node.
The following example shows how to define a folder:

```yaml
name: "machine_name" # name of the machine
machine_category: "machine_category" # category of the machine
machine_type: "machine_type" # type of the machine
machine_model: "machine_model" # model of the machine
description: "machine_description" # description of the machine
root:
  !!FolderNode
  name: "folder"
  description: "folder_description"
  children:
    ...
```

### Variable Nodes

Variable nodes are used to store data values in the data model. They can be of
different types, including boolean, string, numerical, and object.
To create a variable node, you need to specify its type, name, description,
initial value, and any additional attributes specific to the variable type.
The following examples show how to define a folder node with different types of variable nodes:

```yaml
...
  !!FolderNode
    name: "folder"
    description: "folder_description"
    children:
     - !!BooleanVariableNode
       name: "boolean"
       description: "description"
       initial_value: False
     - !!StringVariableNode
       name: "string"
       description: "string_description"
       initial_value: "value"
     - !!NumericalVariableNode
       name: "float"
       description: "float_description"
       # numerical nodes may also have a measure unit
       measure_unit: "LengthUnits.Meter"
       initial_value: 50.0
     - !!ObjectVariableNode
       name: "object"
       description: "object_description"
       properties:
         - !!StringVariableNode
           name: "string"
           initial_value: "value"
         - !!BooleanVariableNode
           name: "boolean"
           initial_value: True
```

Once the data model is defined, you can create an instance of the data model
using the `DataModel` class. The data model is created by loading the YAML file
containing the data model definition. The `DataModel` class provides methods to
read and write variable values, call methods, and manage subscriptions.

```python
from machine_data_model.builder.data_model_builder import DataModelBuilder
from machine_data_model.nodes.variable_node import VariableNode

builder = DataModelBuilder()
data_model = builder.get_data_model("path/to/model.yaml")

node = data_model.get_node("folder1/boolean")
node.value = False
print(f"Node.value : {node.value}")
# Node.value: False

node.subscribe("New User")
print(f"Subscribers: {node.get_subscribers()}")
# Subscribers: ["New User"]

def callback_example(subscriber: str, node: VariableNode, value) -> None:
  print(node.name, "got an update for", subscriber, ":", value)

node.set_subscription_callback(callback_example)
node.value = True
# boolean got an update for New User: True

node.unsubscribe("New User")
print(f"Subscribers: {node.get_subscribers()}")
# Subscribers: []
```

or through the data model:

```python
data_model.write_variable("folder1/boolean", False)
print(f"Node.value : {data_model.read_variable("folder1/boolean")}")
# Node.value: False
```

The nodes also support pre- and post-callbacks, which can be used to execute custom logic
before or after a read or write operation.
This allows for user-defined interactions with the data model.

```python
node.set_pre_read_value_callback(lambda: print("Pre read callback"))
node.set_post_read_value_callback(lambda node_value: print("Post read callback ", node_value))
node.set_pre_update_value_callback(lambda new_value: print("Pre write callback ", new_value))
# post update return a boolean value, which when False cancels the update,
# reverting the value of the node to the previous one
node.set_post_update_value_callback(lambda prev_value, new_value: prev_value != new_value)
```

Object nodes are a special type of variable node that can contain other variable nodes as properties.
Properties of the node can be accessed using the bracket notation, similar to how
you would access properties in a dictionary.

```python
object_node = data_model.get_node("folder1/o_variable2")
print(f"Node.value : {object_node["s_variable3"].value}")
# "variable_value3"
```

### Method Nodes

Method nodes are used to define functions that can be invoked on the data model.
The data model supports three types of method nodes:

- **MethodNode**: A synchronous method that returns only after
  the requested operation completes. The operation may be a long-running
  task, which requires multiple time steps to complete.

```yaml
...
  ...
    !!MethodNode
      name: "method"
      description: "method_description"
      parameters:
        - !!StringVariableNode
          name: "string"
          description: "string_description"
          default_value: "value"
        - !!BooleanVariableNode
          name: "boolean"
          description: "boolean_description"
          default_value: False
      returns:
        - !!NumericalVariableNode
          name: "float"
          description: "float_description"
          measure_unit: "LengthUnits.Meter"
```

- **AsyncMethodNode**: An asynchronous method that returns immediately after
  being invoked.

```yaml
...
  ...
    !AsyncMethodNode
      name: "async_method"
      description: "async_method_description"
      parameters:
        ...
      returns:
        ...
```

- **CompositeMethodNode**: A synchronous method composed of a sequence of
  operations specified in a Control Flow Graph (**CFG**). It allows wrapping
  asynchronous methods in synchronous semantics. The nodes in the CFG can be
  read, write, wait, asynchronous method invocation operations on the data
  model nodes. When invoked, the method executes the operations in the CFG
  in the order they are defined, and returns the result only when all
  operations are completed. If the execution does not terminate (hen
  some wait conditions are not met), it returns the id of execution instance.
  The execution id can be used to resume the execution of the method.

```yaml
...
  ...
    !!CompositeMethodNode
      name: "composite_method"
      description: "composite_method_description"
      parameters:
        ...
      cfg:
        - !!WriteVariableNode
          variable: "folder/float"
          value: 18
        - !!WaitConditionNode
          variable: "folder/float"
          operator: "=="
          rhs: 17
        - !!ReadVariableNode
          variable: "folder/boolean"
          store_as: "var_out"
      returns:
        ...
```

The behavior of the method must be implemented in the target code and bind
to the **callback** attribute of the node.

```python
node = data_model.get_node("folder/method")

def sum_1(i:int) -> int:
  return i + 1

node.callback = sum_1
print(f"Result: {node(1)}")
#Result: 2
```

Similarly to the variable nodes, method nodes can also have pre- and
post-callbacks.
These callbacks enable operations to be executed **before** or **after** the method invocation,
allowing for user-defined interactions with the data model.

#### Requires (preconditions)

Every method node (`MethodNode`, `AsyncMethodNode`, `CompositeMethodNode`) can
declare `requires`: a list of conditions on variables of the data model that
must **all** hold (AND) for the method to be called. A call that does not
satisfy them is rejected before anything runs: no callback, no pre-call, no
execution context.

```yaml
!!MethodNode
  name: "start"
  parameters:
    - !!StringVariableNode
      name: "unit"
      default_value: "/plant/conveyor/mode"
  requires:
    - variable: "/plant/conveyor/mode"
      operator: "=="
      rhs: 2
    - variable: "/plant/conveyor/speed"
      operator: ">="
      rhs: 10
    - variable: "${unit}"
      operator: "!="
      rhs: 0
```

Each condition has exactly the keys `variable`, `operator` and `rhs`.
`variable` is the path or the id of a variable, `operator` is one of `==`,
`!=`, `<`, `>`, `<=`, `>=`, and `rhs` is a literal or a `${name}` template.
A `${name}` (in `variable` or `rhs`) must be the name of a parameter of the
method; this is checked when the method is built. **Always quote the
operator** in YAML: an unquoted `!=` is read as a YAML tag and an unquoted `>=`
as a block scalar indicator. The dumper writes `requires` only when it is not
empty, so models without it are dumped as before.

The conditions are evaluated with the **cached** value of the variables: a
call never reads a remote variable to decide whether it can go on. When the
data model is built, the path of every condition without a `${...}` must name
a variable of the model, otherwise building fails with a `ValueError` that
names the method and the path. A templated path depends on the arguments of
the call and is checked when the method is called.

A rejected call raises `MethodPreconditionError`. Its `error` is an
`ExecutionError` with one of these codes, its `outcomes` lists the outcome of
every condition that was evaluated:

| Code | Meaning | Frost error code |
| --- | --- | --- |
| `PRECONDITION_NOT_MET` | at least one condition does not hold | `NOT_ALLOWED` |
| `NO_DATA` | no condition fails, but one cannot be evaluated: the variable has no value, a remote variable has not received a value yet, or the value cannot be compared | `NOT_ALLOWED` |
| `INVALID_CONFIGURATION` | a condition can never be evaluated: the variable does not exist, is not a variable, is remote without a connector, or a `${name}` is missing from the call | `BAD_REQUEST` |

When several conditions are unmet, the message names the first five and the
number of the others, and the code is chosen over all of them
(`INVALID_CONFIGURATION`, then `PRECONDITION_NOT_MET`, then `NO_DATA`).
The message never contains the value the variable had; that value is in
`error.observed` (bounded, for logs and diagnostics) and is **never sent over
Frost**.

```python
from machine_data_model.nodes.method_node import MethodPreconditionError

method = data_model.get_node("/plant/conveyor/start")

if method.is_executable():          # True only if every condition holds
    method()

try:
    method()
except MethodPreconditionError as error:
    print(error.error.code, error.error.message)

for outcome in method.evaluate_requires():   # diagnostic, runs nothing
    print(outcome.result, outcome.message)
```

`is_executable(**kwargs)` returns `False` when a condition is unmet, has no
data or is misconfigured. `evaluate_requires(**kwargs)` returns the outcome of
each condition and lets a misconfiguration (`ConditionError`) propagate.
Neither of them calls the callbacks or changes a variable.

Through the Frost protocol, an `INVOKE` of a method whose requires are not
satisfied is answered with an error message (see the table); the method is not
invoked. In a control flow graph, a `CallMethodNode` whose callee rejects the
call fails with the same error code (`on_unmet: fail` behavior).

Limits to keep in mind:

- **Remote methods**: `requires` is evaluated locally, in this data model,
  before the call is forwarded to the connector. The remote server may have
  its own checks, which are not visible here.
- **"Received" means "arrived", not "recent"**: a remote variable counts as
  having a value once a value arrived from the remote side (`received_at`, the
  time it arrived in this process). A retained MQTT message or the first read at
  start-up looks fresh. There is no staleness limit, and `received_at` is not
  reset when the connection drops, so a variable keeps its last value after a
  disconnect.
- **Cached value**: a remote variable can have changed since its last update.
  A condition is a guard, not a lock: the state can change between the check
  and the action.
- **No authorization**: the Frost protocol has no authorization. Anyone who can
  send an `INVOKE` can learn from the error text which conditions of a method
  are not met. Do not put secrets in condition paths or right-hand sides.
- **Templated paths are chosen by the caller**: with `variable: "${unit}"`
  the caller picks, through the argument, the variable that is tested, and the
  error text tells whether it matched. Do not template a path over variables
  that must stay private.

## Connectors

Connectors keep the public node API protocol-agnostic. A variable can still be
read with `read()`, written with `write()`, and subscribed to regardless of the
remote backend.

### OPC UA

OPC UA variables map to OPC UA nodes. Reads and writes are performed on the
OPC UA nodes, and method calls are performed on the OPC UA method nodes.

```yaml
connectors:
  - !!OpcUaConnector
    name: "opc_ua_server"
    ip: "127.0.0.1"
    port: 4840

root:
  !!FolderNode
  name: "Objects"
  connector_name: "opc_ua_server"
  children:
    - !!NumericalVariableNode
      name: "Temperature"
      default_value: 20.0
    - !!BooleanVariableNode
      name: "StartCommand"
      default_value: false
      remote_resource_spec:
        !!OpcUaRemoteResourceSpec
        node_id: "ns=2;s=StartCommand"
```

### MQTT

MQTT variables map to MQTT topics. Reads return the last received payload for
the subscription topic, writes publish the value to the publish topic,
and method calls are not supported by the MQTT connector yet.

```yaml
connectors:
  - !!MqttConnector
    name: "mqtt_broker"
    ip: "127.0.0.1"
    port: 1883
    topic_prefix: "machines/boiler-1"
    payload_codec: "string"

root:
  !!FolderNode
  name: "Objects"
  connector_name: "mqtt_broker"
  children:
    - !!NumericalVariableNode
      name: "Temperature"
      default_value: 20.0
    - !!BooleanVariableNode
      name: "StartCommand"
      default_value: false
      remote_resource_spec:
        !!MqttRemoteResourceSpec
        subscribe_topic: "plant/line-1/start/state"
        publish_topic: "plant/line-1/start/set"
```

Supported MQTT payload codecs are `string`, `json`, and `msgpack`. The default
`string` codec encodes strings, integers, floats, and booleans as UTF-8 scalar
payloads and uses the data model node type when deserializing subscribed values.
Python code can also pass `payload_serializer` and `payload_deserializer` to
`MqttConnector` for custom payload formats. Topic wildcards are not supported
in remote resource specs.

## Protocol Manager

The protocol manager is a component that acts as an interface between the data model
and the different protocols used to communicate with the data model.
Currently, the library supports the [FROST](https://github.com/glacier-project/frost.git)
protocol, which is a protocol for communication between machines and
applications in the manufacturing domain.

The protocol manager implements the protocol-specific logic for handling
incoming requests and outgoing responses. It translates the protocol messages
into operations on the data model, allowing users to interact with the data
model using the protocol.

More information about the protocol manager can be found in the directory
`machine_data_model/protocol_manager/`.

## Installation

### From source

#### Pre-requisites

- Python 3.11 or higher
- Poetry 1.8 or higher

#### Building the library

```bash
git clone https://github.com/glacier-project/machine-data-model.git
cd machine-data-model
poetry build
python3.11 -m pip install dist/machine_data_model-0.0.1-py3-none-any.whl
```

### From PyPI

Coming soon!

## Contributing

Contributions are welcome! If you have suggestions for improvements or
features, please open an issue or submit a pull request.

## Development Setup

The development environment is managed with [Poetry](https://python-poetry.org/).
To set up the development environment, follow these steps:

1. Clone the repository
2. Download and install Poetry from the [official website](<https://python-poetry.org/docs/#installation>).
3. execute `poetry install --all-extras` to install the development dependencies.

## Development

Before committing changes, make sure to run tox with `bash scripts/run_tox.sh`.
Tox will test the code with different Python versions, formats the code with
`ruff` and check the types with `mypy`.
In addition, the GitHub Actions can be tested locally with [act](<https://github.com/nektos/act>) using the command `act`.
Additional scripts are available in the `scripts` folder.

**Note**: All the commits must pass a set of pre-commit checks. To manually run
the checks, execute `poetry run pre-commit run --all-files`.
