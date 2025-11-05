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
    A node that represents a composite method in the machine data model.

    Composite methods are composed of multiple asynchronous sub-methods,
    wait conditions, and other control flow elements.

    Attributes:
        _parameters (list[VariableNode]): A list of parameters for the method.
        _returns (list[VariableNode]): A list of return values for the method.
        _callback (Callable[..., Any]): The function to execute when the method is called.
        _pre_call (Callable[..., None]): The function to run before the method is called.
        _post_call (Callable[..., None]): The function to run after the method is called.
        _scopes (dict[str, ControlFlowScope]): A dictionary of scopes for the method.
        cfg (ControlFlow): The control flow graph of the method.
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
        Initializes a new CompositeMethodNode instance.

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
        self._scopes: dict[str, ControlFlowScope] = {}
        self.cfg = cfg if cfg is not None else ControlFlow()

    def __call__(self, *args: Any, **kwargs: Any) -> MethodExecutionResult:
        """
        Calls the method with the specified arguments.

        Args:
            *args (Any): The positional arguments of the method.
            **kwargs (Any): The keyword arguments of the method.

        Returns:
            MethodExecutionResult: The result of the method execution.
        """
        kwargs = self._resolve_arguments(*args, **kwargs)

        self._pre_call(**kwargs)
        return self._start_execution(**kwargs)

    def _terminate_execution(self, scope: ControlFlowScope) -> dict[str, Any]:
        """
        Terminates the execution of the method for a given scope.

        Args:
            scope (ControlFlowScope): The scope of the execution to terminate.

        Returns:
            dict[str, Any]: A dictionary of return values if the method is completed, otherwise the scope id.
        """
        if scope.is_active():
            return {SCOPE_ID: scope.id()}

        ret_t = tuple(scope.get_value(node.name) for node in self.returns)
        ret = self._build_return_dict(ret_t)
        self._post_call(ret)
        return ret

    def is_terminated(self, scope_id: str) -> bool:
        """
        Checks if the scope with the specified id is terminated.

        Args:
            scope_id (str): The id of the scope to check.

        Returns:
            bool: True if the scope is terminated, False otherwise.
        """
        scope = self._get_scope(scope_id)
        return not scope.is_active()

    def delete_scope(self, scope_id: str) -> None:
        """
        Deletes the scope with the specified id.

        Args:
            scope_id (str): The id of the scope to delete.
        """
        if scope_id not in self._scopes:
            raise ValueError(f"Scope '{scope_id}' not found")
        del self._scopes[scope_id]

    def handle_message(self, scope_id: str, message: FrostMessage) -> bool:
        """
        Handles a response message for a remote execution node.

        Args:
            scope_id (str): The id of the scope.
            message (FrostMessage): The response message.

        Returns:
            bool: True if the method can be resumed, False otherwise.
        """
        scope = self._get_scope(scope_id)

        # get current node
        node = self.cfg.get_current_node(scope)
        if not isinstance(node, RemoteExecutionNode):
            return False

        return node.handle_response(scope=scope, response=message)

    def resume_execution(self, scope_id: str) -> MethodExecutionResult:
        """
        Resumes the execution of the method with the specified scope id.

        Args:
            scope_id (str): The id of the scope to resume.

        Returns:
            MethodExecutionResult: The result of resuming the execution.
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
        Starts the execution of the composite method.

        This creates a new scope and executes the control flow graph until a wait
        condition is reached or the method is completed.

        Args:
            **kwargs (dict[str, Any]): The arguments of the method.

        Returns:
            MethodExecutionResult: The result of starting the execution.
        """

        scope = self._create_scope(**kwargs)
        remote_messages = self.cfg.execute(scope)
        return MethodExecutionResult(
            messages=remote_messages, return_values=self._terminate_execution(scope)
        )

    def _get_scope(self, scope_id: str) -> ControlFlowScope:
        """
        Gets the scope with the specified id.

        Args:
            scope_id (str): The id of the scope to get.

        Returns:
            ControlFlowScope: The scope with the specified id.
        """
        return self._scopes[scope_id]

    def _create_scope(self, **kwargs: dict[str, Any]) -> ControlFlowScope:
        """
        Creates a new scope with the specified arguments.

        Args:
            **kwargs (dict[str, Any]): The arguments to create the scope with.

        Returns:
            ControlFlowScope: The created scope.
        """
        scope_id = str(uuid.uuid4())
        scope = ControlFlowScope(scope_id, **kwargs)
        assert scope_id not in self._scopes
        self._scopes[scope_id] = scope
        return scope

    def __str__(self) -> str:
        return f"CompositeMethodNode(id={self.id}, name={self.name}, description={self.description}, parameters={self.parameters}, returns={self.returns})"

    def __eq__(self, other: object) -> bool:
        if self is other:
            return True

        if not isinstance(other, CompositeMethodNode):
            return False

        return super().__eq__(other) and self.cfg == other.cfg
