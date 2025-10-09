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
    A CompositeMethodNode class is a node that represents a composite method in the
    machine data model. Composite methods of the machine data model are used to
    declare functions that are composed of multiple asynchronous sub-methods,
    wait conditions, and other control flow elements.

    :ivar _parameters: A list of parameters for the method.
    :ivar _returns: A list of return values for the method.
    :ivar _callback: The function to execute when the method is called. The callback
    function for a composite method is fixed and cannot be changed. It consists of
    control flow executor that calls the sub-methods in sequence, waits for conditions
    to be met, and executes other control flow elements.
    :ivar _pre_call: The function to run before the method is called.
    :ivar _post_call: The function to run after the method is called.
    :ivar _contexts: A dictionary of contexts for the method. Each context represents a
    separate instance of the method that is being executed. The key of the dictionary
    is the context id, and the value is the context object.
    :ivar cfg: The control flow graph of the method. The control flow graph consists
    of control flow nodes implementing the logic of the method.
    """

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

        :param id: The unique identifier of the method.
        :param name: The name of the method.
        :param description: The description of the method.
        :param parameters: A list of parameters for the method.
        :param returns: A list of return values for the method.
        """
        super().__init__(
            id=id,
            name=name,
            description=description,
            parameters=parameters,
            returns=returns,
        )
        self._contexts: dict[str, ExecutionContext] = {}
        self.cfg = cfg if cfg is not None else ControlFlow(composite_method_node=self)
        if cfg is not None and self.cfg._composite_method_node is None:
            self.cfg._composite_method_node = self

    def __call__(self, *args: Any, **kwargs: Any) -> MethodExecutionResult:
        """
        Call the method with the specified arguments.

        :param args: The positional arguments of the method.
        :param kwargs: The keyword arguments of the method.
        :return: The return values of the method.
        """
        kwargs = self._resolve_arguments(*args, **kwargs)

        self._pre_call(**kwargs)
        return self._start_execution(**kwargs)

    def _terminate_execution(self, context: ExecutionContext) -> dict[str, Any]:
        """
        Terminate the execution of the method with the specified context. It returns the
        return values of the method if the method is completed, otherwise it returns
        the context id.
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

        :param context_id: The id of the context to check.
        :return: True if the context is terminated, False otherwise.
        """
        context = self._get_context(context_id)
        return not context.is_active()

    def delete_context(self, context_id: str) -> None:
        """
        Delete the context with the specified id.

        :param context_id: The id of the context to delete.
        """
        if context_id not in self._contexts:
            raise ValueError(f"context '{context_id}' not found")
        del self._contexts[context_id]

    def handle_message(self, context_id: str, message: FrostMessage) -> bool:
        """Handle the response message in response to the request generated from the execution of the current remote node.

        :param context: The context of the control flow graph.
        :param message: The response to the current remote execution node request.
        :return: True if the method can be resumed, False otherwise.
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

        :param context_id: The id of the context to resume.
        :return: The result of resuming the execution of the method.
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
        Start the execution of the composite method with the specified arguments.
        It creates a new context and executes the control flow graph of the method until
        a wait condition is reached or the method is completed. A context id is returned
        if the method is not completed.

        :param kwargs: The arguments of the method.
        :return: The result of starting the execution of the method.
        """

        context = self._create_context(**kwargs)
        remote_messages = self.cfg.execute(context)
        return MethodExecutionResult(
            messages=remote_messages, return_values=self._terminate_execution(context)
        )

    def _get_context(self, context_id: str) -> ExecutionContext:
        """
        Get the context with the specified id.

        :param context_id: The id of the context to get.
        :return: The context with the specified id.
        """
        return self._contexts[context_id]

    def _create_context(self, **kwargs: dict[str, Any]) -> ExecutionContext:
        """
        Create a new context with the specified arguments.

        :param kwargs: The arguments to create the context with.
        :return: The created context.
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
