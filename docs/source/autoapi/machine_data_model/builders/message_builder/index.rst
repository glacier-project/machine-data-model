machine_data_model.builders.message_builder
===========================================

.. py:module:: machine_data_model.builders.message_builder


Classes
-------

.. autoapisummary::

   machine_data_model.builders.message_builder.MessageBuilder


Module Contents
---------------

.. py:class:: MessageBuilder

   .. py:attribute:: sender
      :type:  str


   .. py:attribute:: target
      :type:  str


   .. py:attribute:: uuid_code


   .. py:attribute:: topology
      :type:  machine_data_model.protocols.glacier_v1.enumeration_for_messages.MessageType


   .. py:attribute:: payload
      :type:  Any


   .. py:method:: set_sender(sender: str) -> MessageBuilder


   .. py:method:: set_target(target: str) -> MessageBuilder


   .. py:method:: set_uuid_code(uuid_code: uuid.UUID) -> MessageBuilder


   .. py:method:: set_topology(topology: machine_data_model.protocols.glacier_v1.enumeration_for_messages.MessageType) -> MessageBuilder


   .. py:method:: set_variable_payload(payload: machine_data_model.protocols.glacier_v1.variable_message.VariableCall) -> MessageBuilder


   .. py:method:: set_method_payload(payload: machine_data_model.protocols.glacier_v1.method_message.MethodCall) -> MessageBuilder


   .. py:method:: build() -> machine_data_model.protocols.glacier_v1.message.Message
