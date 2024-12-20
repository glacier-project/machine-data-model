machine_data_model.protocols.glacier_v1.variable_message
========================================================

.. py:module:: machine_data_model.protocols.glacier_v1.variable_message


Classes
-------

.. autoapisummary::

   machine_data_model.protocols.glacier_v1.variable_message.VarOperation
   machine_data_model.protocols.glacier_v1.variable_message.VariableCall


Module Contents
---------------

.. py:class:: VarOperation(*args, **kwds)

   Bases: :py:obj:`enum.Enum`


   Create a collection of name/value pairs.

   Example enumeration:

   >>> class Color(Enum):
   ...     RED = 1
   ...     BLUE = 2
   ...     GREEN = 3

   Access them by:

   - attribute access:

     >>> Color.RED
     <Color.RED: 1>

   - value lookup:

     >>> Color(1)
     <Color.RED: 1>

   - name lookup:

     >>> Color['RED']
     <Color.RED: 1>

   Enumerations can be iterated over, and know how many members they have:

   >>> len(Color)
   3

   >>> list(Color)
   [<Color.RED: 1>, <Color.BLUE: 2>, <Color.GREEN: 3>]

   Methods can be added to enumerations, and members can have their own
   attributes -- see the documentation for details.


   .. py:attribute:: READ
      :value: 1



   .. py:attribute:: WRITE
      :value: 2



   .. py:attribute:: SUBSCRIBE
      :value: 3



   .. py:attribute:: UNSUBSCRIBE
      :value: 4



.. py:class:: VariableCall

   .. py:attribute:: varname
      :type:  str


   .. py:attribute:: operation
      :type:  VarOperation


   .. py:attribute:: args
      :type:  list


   .. py:method:: has_arg(arg: Any) -> bool


   .. py:property:: to_dict
      :type: dict
