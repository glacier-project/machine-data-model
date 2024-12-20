# GLACIER Machine Data Model

This repository contains the implementation of the machine data model for the GLACIER platform.
The machine data model consists of a structured representation, inspired by
the OPC UA information model, ISA-95 data model, RAMI 4.0, SoM-like data
models and other similar data models.
It implements the machine interface that is used to interact with the
machines in the GLACIER platform.

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

The supported interaction patterns are:
- Read: read the value of a variable
- Write: write the value of a variable
- Call: call a method
- Subscribe: subscribe to a variable to receive updates when its value changes

# TODO:
- [x] Implement the machine data model
  - [x] Machine data model folder
  - [x] Machine data model variable
  - [x] Machine data model method
  - [x] Machine data model object
  - [x] Machine data model
  - [x] Machine data model builder
- [ ] Implement callbacks for reading, writing and method call on the respective
  machine data model nodes
  - [ ] Read callback
  - [ ] Write callback
  - [ ] Method call callback
  - [ ] Subscription callback
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

TODO

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
the checks, execute `poetry pre-commit run --all-files`.
