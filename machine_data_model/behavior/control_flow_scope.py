import re
from typing import Any
from enum import IntEnum

template_re = re.compile(r"\$\{([^}]+)\}")


def is_template_variable(string: str) -> bool:
    """
    Checks if the string is a template variable of the form `${variable_name}`.

    Args:
        string (str): The string to check.

    Returns:
        bool: True if the string is a template variable, False otherwise.
    """
    return bool(template_re.fullmatch(string))


def contains_template_variables(string: str) -> bool:
    """
    Checks if the string contains any template variable of the form `${variable_name}`.

    Args:
        string (str): The string to check.

    Returns:
        bool: True if the string contains at least one template variable, False otherwise.
    """
    return bool(template_re.search(string))


def resolve_string_in_scope(string: str, scope: "ControlFlowScope") -> Any:
    """
    Resolves all template variables in the string using the provided scope.

    A template variable is defined as `${variable_name}` and will be replaced by the
    value of `variable_name` in the scope.

    Args:
        string (str): The string containing template variables to resolve.
        scope ("ControlFlowScope"): The scope to use for resolving variables.

    Returns:
        Any: The resolved string. If the entire string is a single template variable,
             the value of that variable is returned directly.
    """
    if not contains_template_variables(string):
        return string

    if is_template_variable(string):
        match = template_re.fullmatch(string)
        assert match is not None
        return scope.get_value(match.group(1))

    matches = list(template_re.finditer(string))
    for match in reversed(matches):
        variable_name = match.group(1)
        span = match.span()

        # substitute the variable with its value in the scope
        variable_value = str(scope.get_value(variable_name))
        string = string[: span[0]] + variable_value + string[span[1] :]

    return string


def resolve_value(value: Any, scope: "ControlFlowScope") -> Any:
    """
    Resolves the value of a variable in the scope.

    If the value is a string containing template variables, it is resolved using the scope.
    Otherwise, the value is returned as is.

    Args:
        value (Any): The value to resolve.
        scope ("ControlFlowScope"): The scope to use for resolving.

    Returns:
        Any: The resolved value.
    """
    if isinstance(value, str) and contains_template_variables(value):
        return resolve_string_in_scope(value, scope)
    return value


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
    Execution scope for a control flow graph.

    It contains the local variables and the program counter for an execution.

    Attributes:
        _scope_id (str): The unique identifier of the scope.
        _locals (dict[str, Any]): The local variables of the scope.
        _pc (int): The program counter of the scope.
        _status (ControlFlowStatus): The status of the control flow execution.
        active_request (str | None): The correlation id of the active request, if any.
    """

    def __init__(self, scope_id: str, **kwargs: dict[str, Any]):
        """
        Initializes a new `ControlFlowScope` instance.

        Args:
            scope_id (str): The unique identifier of the scope.
            **kwargs (dict[str, Any]): The local variables of the scope.
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

        Args:
            **kwargs (dict[str, Any]): The local variables to set.
        """
        if not self.is_active():
            raise ValueError("Attempt to set values on an inactive scope")

        for key, value in kwargs.items():
            key = resolve_string_in_scope(key, self)
            self._locals[key] = value

    def has_value(self, var_name: str) -> bool:
        """
        Checks if a local variable exists in the scope.

        Args:
            var_name (str): The name of the local variable.

        Returns:
            bool: True if the local variable exists, False otherwise.
        """
        var_name = resolve_string_in_scope(var_name, self)
        return var_name in self._locals

    def get_value(self, var_name: str) -> Any:
        """
        Gets the value of a local variable in the scope.

        Args:
            var_name (str): The name of the local variable.

        Returns:
            Any: The value of the local variable.

        Raises:
            KeyError: If the local variable does not exist.
        """
        var_name = resolve_string_in_scope(var_name, self)
        if var_name not in self._locals:
            raise KeyError(f"Variable '{var_name}' not found in scope {self.locals()}")
        return self._locals[var_name]

    def set_value(self, var_name: str, value: Any) -> None:
        """
        Sets the value of a local variable in the scope.

        Args:
            var_name (str): The name of the local variable.
            value (Any): The value of the local variable.
        """
        self.set_all_values(**{var_name: value})

    def delete_value(self, var_name: str) -> None:
        """
        Deletes a local variable from the scope.

        Args:
            var_name (str): The name of the local variable.
        """
        var_name = resolve_string_in_scope(var_name, self)
        if var_name in self._locals:
            del self._locals[var_name]

    def get_pc(self) -> int:
        """
        Gets the program counter of the scope.

        Returns:
            int: The program counter.
        """
        return self._pc

    def set_pc(self, pc: int) -> None:
        """
        Sets the program counter of the scope.

        Args:
            pc (int): The new program counter.
        """
        self._pc = pc

    def deactivate(self) -> None:
        """
        Deactivates the scope.
        """
        self._status = ControlFlowStatus.COMPLETED

    def is_active(self) -> bool:
        """
        Checks if the scope is active.

        Returns:
            bool: True if the scope is active, False otherwise.
        """
        return self._status not in [
            ControlFlowStatus.COMPLETED,
            ControlFlowStatus.FAILED,
        ]

    @property
    def status(self) -> ControlFlowStatus:
        """
        Gets the status of the control flow execution.

        Returns:
            ControlFlowStatus: The status of the execution.
        """
        return self._status

    @status.setter
    def status(self, status: ControlFlowStatus) -> None:
        """
        Sets the status of the control flow execution.

        Args:
            status (ControlFlowStatus): The new status.
        """
        self._status = status

    def locals(self) -> dict[str, Any]:
        """
        Gets the local variables of the scope.

        Returns:
            dict[str, Any]: The local variables.
        """
        return self._locals

    def id(self) -> str:
        """
        Gets the unique identifier of the scope.

        Returns:
            str: The unique identifier.
        """
        return self._scope_id

    def __str__(self) -> str:
        return f"ControlFlowScope(execution_id={self._scope_id}, pc={self._pc}, status={self._status})"
