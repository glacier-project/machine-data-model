"""
Composite method node implementation for machine data models.

This module provides the CompositeMethodNode class, which represents methods
composed of multiple asynchronous sub-methods, wait conditions, and control
flow elements within the machine data model framework.
"""

from machine_data_model.behavior.control_flow import ControlFlow
from machine_data_model.behavior.execution_context import (
    ExecutionContext,
)
from machine_data_model.behavior.remote_execution_node import RemoteExecutionNode
from machine_data_model.nodes.method_node import MethodNode
from machine_data_model.nodes.variable_node import VariableNode
from typing import Any
import uuid
from machine_data_model.nodes.method_node import MethodExecutionResult
from machine_data_model.protocols.frost_v1.frost_message import FrostMessage


class CompositeMethodNode(MethodNode):
    """
    A CompositeMethodNode class is a node that represents a composite method in
    the machine data model. Composite methods of the machine data model are used
    to declare functions that are composed of multiple asynchronous sub-methods,
    wait conditions, and other control flow elements.

    Attributes:
        _contexts (dict[str, ExecutionContext]):
            A dictionary of contexts for the method. Each context represents a
            separate instance of the method that is being executed. The key of
            the dictionary is the context id, and the value is the context
            object.
        cfg (ControlFlow):
            The control flow graph of the method. The control flow graph
            consists of control flow nodes implementing the logic of the method.
    """

    _contexts: dict[str, ExecutionContext]
    cfg: ControlFlow

    def __init__(
        self,
        id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        parameters: list[VariableNode] | None = None,
        returns: list[VariableNode] | None = None,
        cfg: ControlFlow | None = None,
    ):
        """
        Initialize a new CompositeMethodNode instance.

        Args:
            id (str | None): The unique identifier of the method.
            name (str | None): The name of the method.
            description (str | None): The description of the method.
            parameters (list[VariableNode] | None): A list of parameters for the method.
            returns (list[VariableNode] | None): A list of return values for the method.
            cfg (ControlFlow | None): The control flow graph of the method.
        """
        super().__init__(
            id=id,
            name=name,
            description=description,
            parameters=parameters,
            returns=returns,
        )
        self._contexts = {}
        self.cfg = cfg if cfg is not None else ControlFlow(composite_method_node=self)
        if cfg is not None and self.cfg._composite_method_node is None:
            self.cfg._composite_method_node = self

    def __call__(self, *args: Any, **kwargs: Any) -> MethodExecutionResult:
        """
        Call the method with the specified arguments.

        Args:
            *args (Any):
                The positional arguments of the method.
            **kwargs (Any):
                The keyword arguments of the method.

        Returns:
            MethodExecutionResult:
                The return values of the method.
        """
        kwargs = self._resolve_arguments(*args, **kwargs)

        self._pre_call(**kwargs)
        return self._start_execution(**kwargs)

    def _terminate_execution(self, context: ExecutionContext) -> dict[str, Any]:
        """
        Terminate the execution of the method with the specified context. It
        returns the return values of the method if the method is completed,
        otherwise it returns the context id.
        """
        if context.is_active():
            return {"@context_id": context.id()}

        ret_t = tuple(context.get_value(node.name) for node in self.returns)
        ret = self._build_return_dict(ret_t)
        self._post_call(ret)
        return ret

    def is_terminated(self, context_id: str) -> bool:
        """
        Check if the context with the specified id is terminated.

        Args:
            context_id (str):
                The id of the context to check.

        Returns:
            bool:
                True if the context is terminated, False otherwise.
        """
        context = self._get_context(context_id)
        return not context.is_active()

    def delete_context(self, context_id: str) -> None:
        """
        Delete the context with the specified id.

        Args:
            context_id (str):
                The id of the context to delete.

        Raises:
            ValueError:
                If the context with the specified id is not found.
        """
        if context_id not in self._contexts:
            raise ValueError(f"context '{context_id}' not found")
        del self._contexts[context_id]

    def handle_message(self, context_id: str, message: FrostMessage) -> bool:
        """
        Handle the response message in response to the request generated from
        the execution of the current remote node.

        Args:
            context_id (str):
                The id of the context.
            message (FrostMessage):
                The response to the current remote execution node request.

        Returns:
            bool:
                True if the method can be resumed, False otherwise.
        """
        context = self._get_context(context_id)

        # get current node
        node = self.cfg.get_current_node(context)
        if not isinstance(node, RemoteExecutionNode):
            return False

        return node.handle_response(context=context, response=message)

    def resume_execution(self, context_id: str) -> MethodExecutionResult:
        """
        Resume the execution of the method with the specified context id.

        Args:
            context_id (str):
                The id of the context to resume.

        Returns:
            MethodExecutionResult:
                The result of resuming the execution of the method.

        Raises:
            ValueError:
                If the context with the specified id is not found.
        """

        context = self._get_context(context_id)
        if context is None:
            raise ValueError(f"context '{context_id}' not found")
        remote_messages = self.cfg.execute(context)
        return MethodExecutionResult(
            messages=remote_messages, return_values=self._terminate_execution(context)
        )

    def _start_execution(self, **kwargs: dict[str, Any]) -> MethodExecutionResult:
        """
        Start the execution of the composite method with the specified
        arguments. It creates a new context and executes the control flow graph
        of the method until a wait condition is reached or the method is
        completed. A context id is returned if the method is not completed.

        Args:
            **kwargs (dict[str, Any]):
                The arguments of the method.

        Returns:
            MethodExecutionResult:
                The result of starting the execution of the method.
        """

        context = self._create_context(**kwargs)
        remote_messages = self.cfg.execute(context)
        return MethodExecutionResult(
            messages=remote_messages, return_values=self._terminate_execution(context)
        )

    def _get_context(self, context_id: str) -> ExecutionContext:
        """
        Get the context with the specified id.

        Args:
            context_id (str):
                The id of the context to get.

        Returns:
            ExecutionContext:
                The context with the specified id.
        """
        return self._contexts[context_id]

    def _create_context(self, **kwargs: dict[str, Any]) -> ExecutionContext:
        """
        Create a new context with the specified arguments.

        Args:
            **kwargs (dict[str, Any]):
                The arguments to create the context with.

        Returns:
            ExecutionContext:
                The created context.
        """
        context_id = str(uuid.uuid4())
        context = ExecutionContext(context_id, **kwargs)
        assert context_id not in self._contexts
        self._contexts[context_id] = context
        return context

    def __str__(self) -> str:
        return f"CompositeMethodNode(id={self.id}, name={self.name}, description={self.description}, parameters={self.parameters}, returns={self.returns})"

    def __eq__(self, other: object) -> bool:
        if self is other:
            return True

        if not isinstance(other, CompositeMethodNode):
            return False

        return super().__eq__(other) and self.cfg == other.cfg
