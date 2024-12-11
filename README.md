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

# Installation

TODO

# Contributing

TODO

## Setup

To set up the development environment, follow these steps:

1. Clone the repository
2. execute `poetry install` to install the dependencies.

## Development

Before committing changes, make sure to run the tests with `poetry run pytest` 
and format the code with `sh scripts/apply_cstyle.sh machine_data_model/`.
