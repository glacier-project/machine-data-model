machine_data_model.builders.data_model_builder
==============================================

.. py:module:: machine_data_model.builders.data_model_builder


Classes
-------

.. autoapisummary::

   machine_data_model.builders.data_model_builder.DataModelBuilder


Module Contents
---------------

.. py:class:: DataModelBuilder

   A class to build a data model from a yaml file.


   .. py:attribute:: cache
      :type:  dict[str, machine_data_model.data_model.DataModel]


   .. py:method:: get_data_model(data_model_path: str) -> machine_data_model.data_model.DataModel

      Get a data model from a yaml file.
      :param data_model_path: The path to the yaml file containing the data model.
      :return: The data model created from the yaml file.
