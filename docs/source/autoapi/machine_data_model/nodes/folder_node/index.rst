machine_data_model.nodes.folder_node
====================================

.. py:module:: machine_data_model.nodes.folder_node


Classes
-------

.. autoapisummary::

   machine_data_model.nodes.folder_node.FolderNode


Module Contents
---------------

.. py:class:: FolderNode(id: str | None = None, name: str | None = None, description: str | None = None, children: dict[str, machine_data_model.nodes.data_model_node.DataModelNode] | None = None)

   Bases: :py:obj:`machine_data_model.nodes.data_model_node.DataModelNode`


   A FolderNode class is a node that represents a folder in the machine data model.
   Folders of the machine data model are used to organize the node of the machine data
   model in a hierarchical structure.


   .. py:property:: children
      :type: dict[str, machine_data_model.nodes.data_model_node.DataModelNode]



   .. py:method:: add_child(child: machine_data_model.nodes.data_model_node.DataModelNode) -> None

      Add a child node to the folder.
      :param child: The child node to add to the folder.



   .. py:method:: remove_child(child_name: str) -> None

      Remove a child node from the folder.
      :param child_name: The name of the child node to remove from the folder.



   .. py:method:: has_child(child_name: str) -> bool

      Check if the folder has a child node with the specified name.
      :param child_name: The name of the child node to check.
      :return: True if the folder has a child node with the specified name, False
      otherwise.
