machine_data_model.protocols.glacier_v1.enumeration_for_messages
================================================================

.. py:module:: machine_data_model.protocols.glacier_v1.enumeration_for_messages


Classes
-------

.. autoapisummary::

   machine_data_model.protocols.glacier_v1.enumeration_for_messages.MessageType


Module Contents
---------------

.. py:class:: MessageType(*args, **kwds)

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


   .. py:attribute:: REQUEST
      :value: 1



   .. py:attribute:: SUCCESS
      :value: 2



   .. py:attribute:: ERROR
      :value: 3



   .. py:attribute:: ACCEPTED
      :value: 4
