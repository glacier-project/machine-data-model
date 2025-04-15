# GLACIER Machine Data Model

This repository contains the implementation of the machine data model for the FROST platform.
The machine data model consists of a structured representation, inspired by
the OPC UA information model, ISA-95 data model, RAMI 4.0, SoM-like data
models and other similar data models.
It implements the machine interface that is used to interact with the
machines in the FROST platform.

## Nodes
The data model is structured in a tree-like structure, where each node
represents one of the following:

- Folder: a folder that contains other directories or variables;
- Variable: a variable with a simple data type (string, numeric, boolean) or a
complex data type (object);
- Method: a method that can be called to perform an action on the machine;

Each node has the following attributes:

- Id: a unique identifier for the node
- Name: a human-readable name for the node
- Description: a description of the node
- Value: the initial value of the node (only for variables)
- LowerBound?: the lower bound of the node (only for numerical variables)
- UpperBound?: the upper bound of the node (only for numerical variables)
- Children: the children of the node (only for folders)
- Methods: the methods of the node (only for folders)
- Properties: the properties of the node (only for variables of type object)

### Variable Nodes

StringVariableNode, NumericalVariableNode, BooleanVariableNode and ObjectVariableNode are all class that extend VariableNode class and they enhance it by declaring the variable type.
ObjectVariableNode is similar to a folder node, but it can just contain VariableNode types. Sons of this node notifies the father whenever they get a value update.


### Method Nodes

We developed 3 different kind of MethodNodes:

- AsyncMethodNode: it returns immediately when invoked. New users shall implement a callback and pass it to the node attribute.
- MethodNode: it shall be enhanced in the Frost Platform with Lingua Franca code with callback assignemnt and timely behavior if necessary.
- CompositeMethodNode: it shall be used for complex tasks. Despite it is a MethodNode, it can perform several operations declared in the control flow graph. It can write variables, read their value, wait for a particular condition and call other AsyncMethodNode.


### Operations

The supported interaction patterns are:

- Read: read the value of a variable
- Write: write the value of a variable
- Call: call a method
- Subscribe: subscribe to a variable to receive updates when its value changes


## TODOs

- [x] Implement the machine data model:
  - [x] Machine data model folder
  - [x] Machine data model variable
  - [x] Machine data model method
  - [x] Machine data model object
  - [x] Machine data model
  - [x] Machine data model builder
- [x] Implement callbacks for reading, writing and method call on the respective
  machine data model nodes:
  - [x] Read callback
    - [x] Pre-read callback
    - [x] Post-read callback
  - [x] Update callback
    - [x] Pre-update callback
    - [x] Post-update callback
  - [x] Method call callback
  - [x] Subscription callback
- [ ] Implement machine data model operations. Data model operations are
  operations performed on the machine data model nodes. They change the state
  of the machine data model nodes and/or trigger the respective callbacks.
  - [ ] Read of a machine data model variable
  - [ ] Write of a machine data model variable
  - [ ] Call of a machine data model method
  - [ ] Subscribe to a machine data model variable
- [ ] Implement the first version of the machine data model API (i.e., the
GLACIER v1 API)
  - [ ] Get information about a machine data model node
  - [ ] Read the value of a machine data model variable
  - [ ] Write the value of a machine data model variable
  - [ ] Call a machine data model method
  - [ ] Subscribe to a machine data model variable
  - [ ] Read, write, call and subscribe messages are translated into machine
    data model operations

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
