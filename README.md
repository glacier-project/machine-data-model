# Machine Data Model
This project enables the creation of structured and efficient data models. The machine data model is a structured representation inspired by standards such as the OPC UA information model, ISA-95 data model, RAMI 4.0, SoM-like data models, and others.


## Nodes
The data model is shaped in a tree-like structure, where each node represents one of the following:

- **Folder**: a folder that contains other directories or variables;
- **Variable**: a variable with a simple data type (string, numeric, boolean) or a
complex data type (object);
- **Method**: a method that can be called to perform an action on the machine;

Each node has the following attributes:

- **Id**: a unique identifier for the node;
- **Name**: a human-readable name for the node;
- **Description**: a description of the node;
- **Value**: the initial value of the node (ObjectNodes holds a dict `{"son_name": its_value}`);
- **Parent**: the parent node;

### Folder Nodes
It contains a dict with all its **children**.
It must be the root node in the data model.

```yaml
!!FolderNode
  name: "folder1"
  description: "folder_description1"
  children:
```

### Variable Nodes
Variable nodes compose the data that your model exposes. They have a **value** variable where it's stored the machine state.

You can perform operation on the variable node taking the target node:

```python
node = data_model.get_node("root_folder/boolean")
node.value = False
print(f"Node.value : {node.value}")
#Node.value: False

node.subscribe("New User")
print(f"Subscribers: {node.get_subscribers()}")
#Subscribers: ["New User"]

node.unsubscribe("New User")
print(f"Subscribers: {node.get_subscribers()}")
#Subscribers: []
```

or through the data model:
```python
data_model.write_variable("root_folder/boolean", False)
print(f"Node.value : {data_model.read_variable("root_folder/boolean")}")
#Node.value: False
```


We implemented 4 kind of VariableNode:

1. **BooleanVariableNode**: it stores a boolean variable;

```yaml
!!BooleanVariableNode
  name: "boolean"
  description: ""
  initial_value: False
```

2. **StringVariableNode**: it stores string;

```yaml
!!StringVariableNode
  name: "s_variable5"
  description: "variable_description5"
  initial_value: "variable_value5"
```

3. **NumericalVariableNode**: it stores a numerical variable. It contains a further field, **measure unit** that describes the physical property of the Node;

```yaml
!!NumericalVariableNode
  name: "n_variable7"
  description: "variable_description7"
  measure_unit: "LengthUnits.Meter"
  initial_value: 50
```

4. **ObjectVariableNode**: it contains several VariableNodes. It doesn't store a value, but sons of this node notifies the father whenever they get a value update.

```yaml
!!ObjectVariableNode
  name: "o_variable2"
  description: "variable_description2"
  properties:
    - !!StringVariableNode
      name: "s_variable3"
      description: "variable_description3"
      initial_value: "variable_value3"
    - !!BooleanVariableNode
      name: "boolean_var"
      description: "variable_description4"
      initial_value: True
```

#### Pre and Post Callbacks
All variable nodes, except for **ObjectVariableNodes**, support **pre** and **post** callbacks. These callbacks can be triggered:
- **Before** a read or write request,
- **After** a read or write request,
- Or **both** before and after a read or write request.

This feature allows for custom logic to be executed during variable interactions, enhancing flexibility and control.

#### Subscribers and Subscription Callbacks
Each variable node maintains a list of **subscribers**. Subscribers can register to receive updates whenever the variable's value changes. Additionally, variable nodes can instantiate a **subscription callback**, enabling dynamic and responsive behavior.

#### Object Node Properties
**ObjectVariableNodes** maintain a dictionary of children, referred to as **properties**. This structure allows the object node to seamlessly access and manage the values of its child nodes, fostering a hierarchical and organized data model.

### Method Nodes
Method nodes can be invoked in order to perform operations on the data model. Their behavior must be implemented in the target code and passed to the **callback** attribute.

```python
node = data_model.get_node("root_folder/method")

def sum_1(i:int) -> int:
  return i + 1

node.callback = sum_1
print(f"Result: {node(1)}")
#Result: 2
```

We developed 3 different kind of MethodNodes:

- **MethodNode**: it is designed to be enhanced in the FROST platform with Lingua Franca code, allowing for **callback** assignment and timely behavior when required.

```yaml
!!MethodNode
  name: "method1"
  description: "method_description1"
  parameters:
    - !!StringVariableNode
      name: "s_variable5"
      description: "variable_description5"
      default_value: "variable_value5"
    - !!BooleanVariableNode
      name: "b_variable6"
      description: "variable_description6"
      default_value: False
  returns:
    - !!NumericalVariableNode
      name: "n_variable7"
      description: "variable_description7"
      measure_unit: "LengthUnits.Meter"
```

- **AsyncMethodNode**: it returns immediately when invoked. Users should implement a **callback** function and assign it to the node's attribute to handle the asynchronous behavior.

```yaml
!AsyncMethodNode
  name: "async_method1"
  description: "method_description1"
  parameters:
    - !!StringVariableNode
      name: "s_variable8"
      description: "variable_description5"
      default_value: "variable_value5"
    - !!BooleanVariableNode
      name: "b_variable9"
      description: "variable_description6"
      default_value: False
  returns:
    - !!NumericalVariableNode
      name: "n_variable10"
      description: "variable_description7"
      measure_unit: "LengthUnits.Meter"
```

- **CompositeMethodNode**: it is designed for complex tasks. Although it is a type of MethodNode, it can execute multiple operations defined in a control flow graph (**cfg**). These operations include writing to variables, reading their values, waiting for specific conditions, and invoking other AsyncMethodNodes.

#### Method Node Features

Each method node supports **input assignment** and **result handling** through its `parameters` and `returns` attributes, both of which are `list[VariableNode]`:

- **Parameters**: A list of arguments required by the method.
- **Returns**: A list of results produced by the method.

To leverage these features, populate the `parameters` and `returns` fields in your model file as needed.

#### Pre and Post Callbacks

Both **MethodNode** and **AsyncMethodNode** types include **pre** and **post** callback attributes. These callbacks enable operations to be executed **before** or **after** the method invocation, providing flexibility for custom logic.

#### Control Flow Graph for Object Nodes

```yaml
!!CompositeMethodNode
  name: "simple_composite_method"
  description: ""
  cfg:
    - !!WriteVariableNode
      variable: "folder1/n_variable1"
      value: 18
    - !!WaitConditionNode
      variable: "folder1/n_variable1"
      operator: "=="
      rhs: 17
    - !!ReadVariableNode
      variable: "folder1/boolean"
      store_as: "var_out"
  returns:
    - !!BooleanVariableNode
      name: "var_out"
      description: "variable_description7"
```

For **ObjectVariableNodes**, you can implement a **control flow graph (CFG)** to define complex behaviors. The CFG can include the following node types:

- **WaitConditionNode**: Pauses execution until a specific condition is met.
- **WriteVariableNode**: Writes a value to a variable.
- **ReadVariableNode**: Reads a value from a variable.
- **CallMethodNode**: Invokes a method.

This structure allows for the creation of dynamic and responsive workflows within the data model.

## Operations

The supported interaction patterns are:

- Read: read the value of a variable
- Write: write the value of a variable
- Call: call a method
- Subscribe: subscribe to a variable to receive updates when its value changes

# Protocol Manager
This repository contains the implementation of the machine data model for the [FROST](https://github.com/esd-univr/frost.git) platform inside `examples/ICE`.

#TODO

# Installation
First of all, clone the repository:

`git clone https://github.com/esd-univr/frost-machine-data-model.git`

Then build the wheel:

`poetry build`

Install through pip:

`pip install dist/machine_data_model-0.0.0-py3-none-any.whl`

# Contributing

TODO

## Development Setup

The development environment is managed with [Poetry](https://python-poetry.org/).
To set up the development environment, follow these steps:

1. Clone the repository
2. Download and install Poetry from the [official website]
   (https://python-poetry.org/docs/#installation).
3. execute `poetry install --all-extras` to install the development dependencies.

## Development

Before committing changes, make sure to run tox with `bash scripts/run_tox.sh`.
Tox will test the code with different Python versions, formats the code with
`ruff` and check the types with `mypy`.
In addition, the GitHub Actions can be tested locally with [act]
(https://github.com/nektos/act) using the command `act`.
Additional scripts are available in the `scripts` folder.

**Note**: All the commits must pass a set of pre-commit checks. To manually run
the checks, execute `poetry run pre-commit run --all-files`.
