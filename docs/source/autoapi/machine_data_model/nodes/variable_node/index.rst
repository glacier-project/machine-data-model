machine_data_model.nodes.variable_node
======================================

.. py:module:: machine_data_model.nodes.variable_node


Classes
-------

.. autoapisummary::

   machine_data_model.nodes.variable_node.VariableNode
   machine_data_model.nodes.variable_node.NumericalVariableNode
   machine_data_model.nodes.variable_node.StringVariableNode
   machine_data_model.nodes.variable_node.BooleanVariableNode
   machine_data_model.nodes.variable_node.ObjectVariableNode


Module Contents
---------------

.. py:class:: VariableNode(id: str | None = None, name: str | None = None, description: str | None = None)

   Bases: :py:obj:`machine_data_model.nodes.data_model_node.DataModelNode`


   A VariableNode class is a node that represents an instance of a variable in the
   machine data model. Variables of the machine data model are used to store the
   current value of a machine data or parameter.


   .. py:method:: read() -> Any

      Get the value of the variable node.
      :return: The value of the variable node.



   .. py:method:: update(value: Any) -> bool

      Update the value of the variable node.
      :param value: The new value of the variable node.
      :return: True if the value was updated successfully, False otherwise.



   .. py:method:: set_pre_read_value_callback(callback: collections.abc.Callable[[], None]) -> None

      Set a callback to be executed before reading the value of the variable.
      :param callback: The callback to be executed before reading the value of the
      variable.



   .. py:method:: set_post_read_value_callback(callback: collections.abc.Callable[Ellipsis, Any]) -> None

      Set a callback to be executed after reading the value of the variable.
      :param callback: The callback to be executed after reading the value of the
      variable.



   .. py:method:: set_pre_update_value_callback(callback: collections.abc.Callable[Ellipsis, Any]) -> None

      Set a callback to be executed before updating the value of the variable.
      :param callback: The callback to be executed before updating the value of the
      variable.



   .. py:method:: set_post_update_value_callback(callback: collections.abc.Callable[Ellipsis, bool]) -> None

      Set a callback to be executed after updating the value of the variable.
      :param callback: The callback to be executed after updating the value of the
      variable.



.. py:class:: NumericalVariableNode(id: str | None = None, name: str | None = None, description: str | None = None, measure_unit: enum.Enum | str = NoneMeasureUnits.NONE, value: float = 0)

   Bases: :py:obj:`VariableNode`


   A NumericalVariableNode class is a node that represents an instance of a variable
   with a numerical value in the machine data model.


.. py:class:: StringVariableNode(id: str | None = None, name: str | None = None, description: str | None = None, value: str = '')

   Bases: :py:obj:`VariableNode`


   A StringVariableNode class is a node that represents an instance of a variable with
   a string value in the machine data model.


.. py:class:: BooleanVariableNode(id: str | None = None, name: str | None = None, description: str | None = None, value: bool = False)

   Bases: :py:obj:`VariableNode`


   A BooleanVariableNode class is a node that represents an instance of a variable with
   a boolean value in the machine data model.


.. py:class:: ObjectVariableNode(id: str | None = None, name: str | None = None, description: str | None = None, properties: dict[str, VariableNode] | None = None, value: dict[str, Any] | None = None)

   Bases: :py:obj:`VariableNode`


   An ObjectVariableNode class is a node that represents an instance of a variable with
   an object value in the machine data model.


   .. py:method:: add_property(property_node: VariableNode) -> None

      Add a property to the object variable.
      :param property_node: The property node to add to the object variable.



   .. py:method:: remove_property(property_name: str) -> None

      Remove a property from the object variable.
      :param property_name: The name of the property to remove from the object
      variable.



   .. py:method:: has_property(property_name: str) -> bool

      Check if the object variable has a property.
      :param property_name: The name of the property to check.
      :return: True if the object variable has the property, False otherwise.



   .. py:method:: get_property(property_name: str) -> VariableNode

      Get a property of the object variable.
      :param property_name: The name of the property to get.
      :return: The property of the object variable.
