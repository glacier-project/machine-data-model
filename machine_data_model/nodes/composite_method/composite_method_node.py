from machine_data_model.behavior.control_flow import ControlFlow
from machine_data_model.behavior.control_flow_scope import (
    ControlFlowScope,
)
from machine_data_model.behavior.remote_execution_node import RemoteExecutionNode
from machine_data_model.nodes.method_node import MethodNode
from machine_data_model.nodes.variable_node import VariableNode
from typing import Any
import uuid
from machine_data_model.nodes.method_node import MethodExecutionResult
from machine_data_model.protocols.frost_v1.frost_message import FrostMessage


SCOPE_ID = "@scope_id"


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
    :ivar _scopes: A dictionary of scopes for the method. Each scope represents a
    separate instance of the method that is being executed. The key of the dictionary
    is the scope id, and the value is the scope object.
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
        self._scopes: dict[str, ControlFlowScope] = {}
        self.cfg = cfg if cfg is not None else ControlFlow()

    def __call__(
        self, *args: list[Any], **kwargs: dict[str, Any]
    ) -> MethodExecutionResult:
        """
        Call the method with the specified arguments.

        :param args: The positional arguments of the method.
        :param kwargs: The keyword arguments of the method.
        :return: The return values of the method.
        """
        kwargs = self._resolve_arguments(*args, **kwargs)

        self._pre_call(**kwargs)
        return self._start_execution(**kwargs)

    def _terminate_execution(self, scope: ControlFlowScope) -> dict[str, Any]:
        """
        Terminate the execution of the method with the specified scope. It returns the
        return values of the method if the method is completed, otherwise it returns
        the scope id.
        """
        if scope.is_active():
            return {SCOPE_ID: scope.id()}

        ret_t = tuple(scope.get_value(node.name) for node in self.returns)
        ret = self._build_return_dict(ret_t)
        self._post_call(ret)
        return ret

    def is_terminated(self, scope_id: str) -> bool:
        """
        Check if the scope with the specified id is terminated.

        :param scope_id: The id of the scope to check.
        :return: True if the scope is terminated, False otherwise.
        """
        scope = self._get_scope(scope_id)
        return not scope.is_active()

    def delete_scope(self, scope_id: str) -> None:
        """
        Delete the scope with the specified id.

        :param scope_id: The id of the scope to delete.
        """
        if scope_id not in self._scopes:
            raise ValueError(f"Scope '{scope_id}' not found")
        del self._scopes[scope_id]

    def handle_message(self, scope_id: str, message: FrostMessage) -> bool:
        """Handle the response message in response to the request generated from the execution of the current remote node.

        :param scope: The scope of the control flow graph.
        :param message: The response to the current remote execution node request.
        :return: True if the method can be resumed, False otherwise.
        """
        scope = self._get_scope(scope_id)

        # get current node
        node = self.cfg.get_current_node(scope)
        if not isinstance(node, RemoteExecutionNode):
            return False

        return node.handle_response(scope=scope, response=message)

    def resume_execution(self, scope_id: str) -> MethodExecutionResult:
        """
        Resume the execution of the method with the specified scope id.

        :param scope_id: The id of the scope to resume.
        :return: The result of resuming the execution of the method.
        """

        scope = self._get_scope(scope_id)
        if scope is None:
            raise ValueError(f"Scope '{scope_id}' not found")
        remote_messages = self.cfg.execute(scope)
        return MethodExecutionResult(
            messages=remote_messages, return_values=self._terminate_execution(scope)
        )

    def _start_execution(self, **kwargs: dict[str, Any]) -> MethodExecutionResult:
        """
        Start the execution of the composite method with the specified arguments.
        It creates a new scope and executes the control flow graph of the method until
        a wait condition is reached or the method is completed. A scope id is returned
        if the method is not completed.

        :param kwargs: The arguments of the method.
        :return: The result of starting the execution of the method.
        """

        scope = self._create_scope(**kwargs)
        remote_messages = self.cfg.execute(scope)
        return MethodExecutionResult(
            messages=remote_messages, return_values=self._terminate_execution(scope)
        )

    def _get_scope(self, scope_id: str) -> ControlFlowScope:
        """
        Get the scope with the specified id.

        :param scope_id: The id of the scope to get.
        :return: The scope with the specified id.
        """
        return self._scopes[scope_id]

    def _create_scope(self, **kwargs: dict[str, Any]) -> ControlFlowScope:
        """
        Create a new scope with the specified arguments.

        :param kwargs: The arguments to create the scope with.
        :return: The created scope.
        """
        scope_id = str(uuid.uuid4())
        scope = ControlFlowScope(scope_id, **kwargs)
        assert scope_id not in self._scopes
        self._scopes[scope_id] = scope
        return scope

    def __str__(self) -> str:
        return f"CompositeMethodNode(id={self.id}, name={self.name}, description={self.description}, parameters={self.parameters}, returns={self.returns})"
