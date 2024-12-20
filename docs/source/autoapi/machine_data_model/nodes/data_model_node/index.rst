machine_data_model.nodes.data_model_node
========================================

.. py:module:: machine_data_model.nodes.data_model_node


Classes
-------

.. autoapisummary::

   machine_data_model.nodes.data_model_node.DataModelNode


Module Contents
---------------

.. py:class:: DataModelNode(id: str | None = None, name: str | None = None, description: str | None = None)

   Bases: :py:obj:`abc.ABC`


   Abstract class for a node in the machine data model.

   Attributes:
       _id: The unique identifier of the node.
       _name: The name of the node.
       _description: The description of the node.


   .. py:property:: id
      :type: str



   .. py:property:: name
      :type: str



   .. py:property:: description
      :type: str
