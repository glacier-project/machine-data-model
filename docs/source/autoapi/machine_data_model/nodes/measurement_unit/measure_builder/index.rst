machine_data_model.nodes.measurement_unit.measure_builder
=========================================================

.. py:module:: machine_data_model.nodes.measurement_unit.measure_builder


Classes
-------

.. autoapisummary::

   machine_data_model.nodes.measurement_unit.measure_builder.NoneMeasureUnits
   machine_data_model.nodes.measurement_unit.measure_builder.NoneMeasure
   machine_data_model.nodes.measurement_unit.measure_builder.MeasureBuilder


Functions
---------

.. autoapisummary::

   machine_data_model.nodes.measurement_unit.measure_builder.get_measure_builder


Module Contents
---------------

.. py:class:: NoneMeasureUnits(*args, **kwds)

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


   .. py:attribute:: NONE
      :value: 0



.. py:class:: NoneMeasure(value: float, from_unit: NoneMeasureUnits = NoneMeasureUnits.NONE)

   Bases: :py:obj:`unitsnet_py.abstract_unit.AbstractMeasure`


   NoneMeasure represents a value with no unit.

   Args:
       value (float): The value.
       from_unit (NoneMeasureUnits): The unit of the value, always
           NoneMeasureUnits.NONE.


   .. py:property:: base_value
      :type: float



   .. py:method:: to_string(unit: NoneMeasureUnits = NoneMeasureUnits.NONE, fractional_digits: int | None = None) -> str

      Format the NoneMeasure to a string.

      Args:
          unit (str): The unit to format the NoneMeasure. The only one available is
              'NONE'.
          fractional_digits (int, optional): The number of fractional digits to keep.

      Returns:
          str: The string format of the NoneMeasure.



   .. py:method:: get_unit_abbreviation(unit_abbreviation: NoneMeasureUnits = NoneMeasureUnits.NONE) -> str

      Get NoneMeasure unit abbreviation.
      Note! the only available unit is 'NONE', so the method will always return an
      empty string.



.. py:class:: MeasureBuilder

   A MeasureBuilder class is a utility builder class used to create a measure object
   from a value and a unit.


   .. py:method:: get_measure_unit(unit: str | enum.Enum) -> enum.Enum


   .. py:method:: create_measure(value: float, unit: str | enum.Enum) -> unitsnet_py.abstract_unit.AbstractMeasure


.. py:function:: get_measure_builder() -> MeasureBuilder

   Get the MeasureBuilder instance.
   :return: The MeasureBuilder instance.
