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
the call and is checked when the method is called. The check runs once, when
the `DataModel` is built: a method added to the model afterwards (or a
parameter added or removed afterwards) is only checked when it is called, and a
problem is then reported as `INVALID_CONFIGURATION`.

The `rhs` is read by the YAML parser, which applies the YAML 1.1 rules of
PyYAML: an unquoted `yes`, `no`, `on` or `off` becomes a boolean, `0x10` is the
integer 16, `010` is 8, `1_000` is 1000, `12:30:00` is an integer (sexagesimal),
`2024-01-31` is a date, and `null` or `~` is `None`. Quote the value
(`rhs: "yes"`) when you mean a string. A `${name}` template is only resolved
when `rhs` is a string; it is rejected inside a list or a mapping.
In a string `rhs` (or `variable`) every `${...}` is a template: there is no
escape for a literal `${x}`. Writing `$${x}` or `\${x}` still resolves the
template and keeps the extra character (`$` or `\`) in front of the value.

A rejected call raises `MethodPreconditionError`. Its `error` is an
`ExecutionError` with one of these codes, its `outcomes` lists the outcome of
every condition that was evaluated:

| Code | Meaning | Frost error code |
| --- | --- | --- |
| `PRECONDITION_NOT_MET` | at least one condition does not hold | `NOT_ALLOWED` |
| `NO_DATA` | no condition fails, but one cannot be evaluated: the variable has no value, a remote variable has not received a value yet, or the value cannot be compared | `NOT_ALLOWED` |
| `INVALID_CONFIGURATION` | a condition can never be evaluated: the variable does not exist, is not a variable, is remote without a connector, or a `${name}` is missing from the call | `UNKNOWN` (a server-side fault, not a mistake of the caller) |

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
invoked.

##### Calling a method with requires from a control flow graph

A `CallMethodNode` that calls a method with `requires` must say what to do when
they do not hold, with `on_unmet`:

```yaml
- !!CallMethodNode
  method: "/plant/start"
  on_unmet: "fail"        # fail the node at once

- !!CallMethodNode
  method: "/plant/start"
  on_unmet: "wait"        # keep waiting, try again when a variable changes
  timeout: 30.0           # optional, in seconds
```

- There is no default. Without `on_unmet` the node fails with
  `INVALID_CONFIGURATION` **before the call, whether the requires hold or
  not**, so a model that is wrong fails every time and not only when a
  condition happens to be unmet. When the data model is built, every such node
  is reported once with a warning that names the composite method, the index of
  the node and the callee. Build the model with
  `DataModelBuilder(strict_requires=True)` (or
  `DataModel(..., strict_requires=True)`) to make it an error. The option is an
  argument, not a key of the YAML file. A callee that is only known at run time
  (a templated path) is checked when the node runs; `on_unmet` on a callee that
  has no `requires` is accepted and has no effect. Remote call nodes
  (`CallRemoteMethodNode`) are not concerned.
- `fail`: the node fails with the code and message of the rejection
  (`PRECONDITION_NOT_MET`, `NO_DATA` or `INVALID_CONFIGURATION`), prefixed with
  the name of the callee.
- `wait`: the node stays running and subscribes to **every** variable that the
  requires of the callee read (a condition that holds can still stop holding).
  When one of them changes, the call is tried again, and it is made only if the
  requires hold at that moment: the check and the call are one step, there is
  no separate wait followed by a call. A condition that can never be evaluated
  (`INVALID_CONFIGURATION`: a missing variable, a remote variable without a
  connector) is never waited on.
- `timeout` is a number of seconds greater than zero and is only accepted with
  `on_unmet: wait`. The clock starts at the first wait. When it runs out, the
  call is tried one last time, and only if the requires still do not hold the
  node fails with `TIMEOUT`, whose message names the callee and the last unmet
  conditions. Write fractions as `1.0e-7`, not `1e-7`: PyYAML reads the latter
  as a string.
- The wait is removed (subscriptions, deadline) whenever the node ends, fails
  or is aborted. It is traced like a `WaitConditionNode` (`wait_start` and
  `wait_end`).

A complete model with both modes is in `examples/requires/requires.yml`, and
`examples/requires/requires.py` loads it in strict mode and tries it.

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
- **Nothing wakes a waiting node by itself**: there is no timer. A `wait`, and
  its `timeout`, advance only when something resumes the context: a change of
  one of the watched variables, or a call to `resume_execution`. A node that
  waits on a variable that never changes is not woken at the deadline; it
  times out the next time it is resumed.
- **A `wait` on a remote variable that never received a value**: such a
  variable gives `NO_DATA` ("no value received yet") until the connector
  delivers a value, and a confirmed write does not count as one. With a
  connector that never reports changes the wait does not end by itself:
  its `timeout` is only checked when something resumes the context (a
  change or `resume_execution`), and nothing does. Set a `timeout` anyway
  and make sure something resumes the context. The mapping of connector
  failures (connection lost, timeout, closed connector) to `NO_DATA` is
  tested with mocks only, not against a live OPC UA server.
- **Templated paths are chosen by the caller**: with `variable: "${unit}"`
  the caller picks, through the argument, the variable that is tested, and the
  error text tells whether it matched. Do not template a path over variables
  that must stay private.
- **No thread safety**: connector threads and the Frost handlers run
  without a lock, so races are known (for example between a variable
  change and a check). A single executor thread is a follow-up.
- **One correlation id per context**: all the remote requests of one
  context share one correlation id, so a late or duplicate answer can be
  taken for the answer to the next request sent to the same remote.
- **A plain `MethodNode` that raises over Frost**: if its callback raises
  while the method is called through the Frost protocol, the request is
  left unanswered (this was already so before `requires`).

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
