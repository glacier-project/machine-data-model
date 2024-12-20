machine_data_model.nodes.method_node
====================================

.. py:module:: machine_data_model.nodes.method_node


Classes
-------

.. autoapisummary::

   machine_data_model.nodes.method_node.MethodNode


Module Contents
---------------

.. py:class:: MethodNode(id: str | None = None, name: str | None = None, description: str | None = None, parameters: list[machine_data_model.nodes.variable_node.VariableNode] | None = None, returns: list[machine_data_model.nodes.variable_node.VariableNode] | None = None, callback: collections.abc.Callable[Ellipsis, Any] | None = None)

   Bases: :py:obj:`machine_data_model.nodes.data_model_node.DataModelNode`


   A MethodNode class is a node that represents a method in the machine data model.
   Methods of the machine data model are used to declare functions that can be executed
   on the machine data model.


   .. py:property:: parameters
      :type: list[machine_data_model.nodes.variable_node.VariableNode]



   .. py:method:: add_parameter(parameter: machine_data_model.nodes.variable_node.VariableNode) -> None

      Add a parameter to the method.
      :param parameter: The parameter to add to the method.



   .. py:method:: remove_parameter(parameter: machine_data_model.nodes.variable_node.VariableNode) -> None

      Remove a parameter from the method.
      :param parameter: The parameter to remove from the method.



   .. py:property:: returns
      :type: list[machine_data_model.nodes.variable_node.VariableNode]



   .. py:method:: add_return_value(return_value: machine_data_model.nodes.variable_node.VariableNode) -> None

      Add a return value to the method.
      :param return_value: The return value to add to the method.



   .. py:method:: remove_return_value(return_value: machine_data_model.nodes.variable_node.VariableNode) -> None

      Remove a return value from the method.
      :param return_value: The return value to remove from the method.



   .. py:property:: callback
      :type: collections.abc.Callable
