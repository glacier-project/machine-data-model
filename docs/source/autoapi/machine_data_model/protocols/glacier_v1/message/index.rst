machine_data_model.protocols.glacier_v1.message
===============================================

.. py:module:: machine_data_model.protocols.glacier_v1.message


Classes
-------

.. autoapisummary::

   machine_data_model.protocols.glacier_v1.message.Message


Module Contents
---------------

.. py:class:: Message

   .. py:attribute:: sender
      :type:  str


   .. py:attribute:: target
      :type:  str


   .. py:attribute:: uuid_code
      :type:  uuid.UUID


   .. py:attribute:: topology
      :type:  machine_data_model.protocols.glacier_v1.enumeration_for_messages.MessageType


   .. py:attribute:: payload
      :type:  Any


   .. py:method:: set_uuid_code(code: uuid.UUID) -> bool


   .. py:property:: to_dict
      :type: dict
