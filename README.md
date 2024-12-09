# GLACIER Machine Data Model

This repository contains the implementation of the machine data model for the GLACIER platform.
The machine data model consists of a structured representation, inspired by 
the OPC UA information model, ISA-95 data model, RAMI 4.0, SoM-like data 
models and other similar data models.
It implements the machine interface that is used to interact with the 
machines in the GLACIER platform.

The data model is structured in a tree-like structure, where each node 
represents one of the following:
- Directory: a directory that contains other directories or variables;
- Variable: a variable with a simple data type (e.g., string, integer, 
  float, boolean) or a complex data type (e.g., object, list, dictionary);
- Method: a method that can be called to perform an action on the machine;

Each node has the following attributes:
- Id: a unique identifier for the node
- Name: a human-readable name for the node
- Description: a description of the node
- Type: the type of the node (e.g., Directory, Method, boolean, intX)
- Value: the initial value of the node (only for variables)
- LowerBound: the lower bound of the node (only for numerical variables)
- UpperBound: the upper bound of the node (only for numerical variables)
- Children: the children of the node (only for directories)
- Methods: the methods of the node (only for directories)
- Properties: the properties of the node (only for variables of type object and dictionary)

The supported interaction patterns are:
- Read: read the value of a variable
- Write: write the value of a variable
- Call: call a method
- Subscribe: subscribe to a variable to receive updates when its value changes

The supported data types are:
- boolean: a boolean value (true or false)
- intX: a signed integer value with X bits
- uintX: an unsigned integer value with X bits
- floatX: a floating-point value with X bits
- string: a string value
- object: a complex data type that contains other variables
- list: a list of values
- dictionary: a dictionary of key-value pairs

# Installation

TODO

# Contributing

TODO

## Setup

To set up the development environment, follow these steps:

TODO
Poetry? Pipenv? Conda?


