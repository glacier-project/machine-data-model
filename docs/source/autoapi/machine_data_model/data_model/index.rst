machine_data_model.data_model
=============================

.. py:module:: machine_data_model.data_model


Classes
-------

.. autoapisummary::

   machine_data_model.data_model.DataModel


Module Contents
---------------

.. py:class:: DataModel(name: str = '', machine_category: str = '', machine_type: str = '', machine_model: str = '', description: str = '', root: machine_data_model.nodes.folder_node.FolderNode | None = None)

   .. py:property:: name
      :type: str



   .. py:property:: machine_category
      :type: str



   .. py:property:: machine_type
      :type: str



   .. py:property:: machine_model
      :type: str



   .. py:property:: description
      :type: str



   .. py:property:: root
      :type: machine_data_model.nodes.folder_node.FolderNode



   .. py:method:: get_node_from_path(path: str) -> machine_data_model.nodes.data_model_node.DataModelNode

      Get a node from the data model by path.
      :param path: The path of the node to get from the data model.
      :return: The node with the specified path.



   .. py:method:: get_node_from_id(node_id: str) -> machine_data_model.nodes.data_model_node.DataModelNode

      Get a node from the data model by id.
      :param node_id: The id of the node to get from the data model.
      :return: The node with the specified id.
