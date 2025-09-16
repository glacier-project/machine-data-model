from typing import Any
from enum import IntEnum


class ControlFlowStatus(IntEnum):
    """
    Enumeration representing the status of a control flow graph execution.

    :cvar READY: The control flow graph is ready to be executed.
    :cvar RUNNING: The control flow graph is currently being executed.
    :cvar WAITING_FOR_EVENT: The control flow graph is waiting for a local event to occur.
    :cvar WAITING_FOR_RESPONSE: The control flow graph is waiting for a response of the remote execution identified by the current program counter.
    :cvar RESPONSE_RECEIVED: The control flow graph has received the response from the remote execution and can continue execution.
    :cvar COMPLETED: The control flow graph has completed execution.
    :cvar FAILED: The control flow graph has failed during execution.
    """

    READY = 0
    RUNNING = 1
    WAITING_FOR_EVENT = 2
    WAITING_FOR_RESPONSE = 3
    RESPONSE_RECEIVED = 4
    COMPLETED = 5
    FAILED = 6


class ControlFlowScope:
    """
    Execution scope for a control flow graph. It contains the local variables and the program counter
    of the control flow graph execution.

    :ivar _scope_id: The unique identifier of the scope.
    :ivar _locals: The local variables of the scope.
    :ivar _pc: The program counter of the scope.
    :ivar _status: The status of the control flow graph execution.
    :ivar active_request: The correlation id of the active request, if any.
    """

    def __init__(self, scope_id: str, **kwargs: dict[str, Any]):
        """
        Initializes a new `ControlFlowScope` instance.

        :param scope_id: The unique identifier of the scope.
        :param kwargs: The local variables of the scope.
        """
        self._scope_id = scope_id
        self._locals: dict[str, Any] = {}  # local variables
        self._pc = 0  # program counter
        self._status = ControlFlowStatus.READY
        self.active_request: str | None = None
        self.set_all_values(**kwargs)

    def set_all_values(self, **kwargs: dict[str, Any]) -> None:
        """
        Sets the values of the local variables in the scope.

        :param kwargs: The local variables to set in the scope.
        """
        if not self.is_active():
            raise ValueError("Attempt to set values on an inactive scope")

        for key, value in kwargs.items():
            self._locals[key] = value

    def get_value(self, var_name: str) -> Any:
        """
        Gets the value of a local variable in the scope.

        :param var_name: The name of the local variable.
        :return: The value of the local variable.
        """
        return self._locals[var_name]

    def resolve_template_variable(self, string: str) -> Any:
        """
        Resolve a string that may contain variable references in the scope.

        :param string: The string to resolve.
        :return: The resolved string with variable references replaced by their values.
        """
        res = string
        before = ""
        after = ""
        result = ""
        while "${" in res and "}" in res:
            before = res.split("${")[0]
            result = res.split("${", 1)[1]
            after = result.split("}", 1)[1]
            result = result.split("}")[0]
            assert self._locals[
                result
            ], f"Variable '{result}' not found in scope {self._locals}"
            result = str(self._locals[result][0])
            res = before + result + after
        return res

    def set_value(self, var_name: str, value: Any) -> None:
        """
        Sets the value of a local variable in the scope.

        :param var_name: The name of the local variable.
        :param value: The value of the local variable.
        """
        self.set_all_values(**{var_name: value})

    def get_pc(self) -> int:
        """
        Get the program counter of the scope.

        :return: The program counter of the scope.
        """
        return self._pc

    def set_pc(self, pc: int) -> None:
        """
        Write the program counter of the scope.

        :param pc: The new program counter of the scope.
        """
        self._pc = pc

    def deactivate(self) -> None:
        """
        Deactivate the scope.
        """
        self._status = ControlFlowStatus.COMPLETED

    def is_active(self) -> bool:
        """
        Check if the scope is active.

        :return: True if the scope is active, False otherwise.
        """
        return self._status not in [
            ControlFlowStatus.COMPLETED,
            ControlFlowStatus.FAILED,
        ]

    @property
    def status(self) -> ControlFlowStatus:
        """
        Get the status of the control flow graph execution.

        :return: The status of the control flow graph execution.
        """
        return self._status

    @status.setter
    def status(self, status: ControlFlowStatus) -> None:
        """
        Set the status of the control flow graph execution.

        :param status: The new status of the control flow graph execution.
        """
        self._status = status

    def locals(self) -> dict[str, Any]:
        """
        Get the local variables of the scope.

        :return: The local variables of the scope.
        """
        return self._locals

    def id(self) -> str:
        """
        Get the unique identifier of the scope.

        :return: The unique identifier of the scope.
        """
        return self._scope_id

    def __str__(self) -> str:
        return f"ControlFlowScope(execution_id={self._scope_id}, pc={self._pc}, status={self._status})"
