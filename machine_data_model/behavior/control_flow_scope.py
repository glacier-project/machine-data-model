import re
from typing import Any
from enum import IntEnum

template_re = re.compile(r"\$\{([^}]+)\}")


def is_template_variable(string: str) -> bool:
    """Check if the string is a template variable of the form `${variable_name}`.

    :param string: The string to check.
    :return: True if the string is a template variable, False otherwise.
    """
    return bool(template_re.fullmatch(string))


def contains_template_variables(string: str) -> bool:
    """Check if the string contains any template variable of the form `${variable_name}`.

    :param string: The string to check.
    :return: True if the string contains at least one template variable, False otherwise.
    """
    return bool(template_re.search(string))


def resolve_string_in_scope(string: str, scope: "ControlFlowScope") -> Any:
    """Resolve all template variables in the string using the provided scope.
    A template variable is defined as `${variable_name}` and will be replaced by the value of `variable_name` in the scope.

    :param string: The string containing template variables to resolve.
    :param scope: The scope to use for resolving template variables.
    :return: The string with all template variables resolved. If the entire string is a single template variable, the value of that variable is returned directly.
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
    Resolve the value of a variable in the scope. If the value is a string containing template variables, it is resolved using the scope. Otherwise, the value is returned as is.

    :param value: The value to resolve.
    :param scope: The scope to use for resolving template variables.
    :return: The resolved value.
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
            key = resolve_string_in_scope(key, self)
            self._locals[key] = value

    def has_value(self, var_name: str) -> bool:
        """
        Checks if a local variable exists in the scope.

        :param var_name: The name of the local variable.
        :return: True if the local variable exists, False otherwise.
        """
        var_name = resolve_string_in_scope(var_name, self)
        return var_name in self._locals

    def get_value(self, var_name: str) -> Any:
        """
        Gets the value of a local variable in the scope.

        :param var_name: The name of the local variable.
        :return: The value of the local variable.
        :raises KeyError: If the local variable does not exist in the scope.
        """
        var_name = resolve_string_in_scope(var_name, self)
        if var_name not in self._locals:
            raise KeyError(f"Variable '{var_name}' not found in scope {self.locals()}")
        return self._locals[var_name]

    def set_value(self, var_name: str, value: Any) -> None:
        """
        Sets the value of a local variable in the scope.

        :param var_name: The name of the local variable.
        :param value: The value of the local variable.
        """
        self.set_all_values(**{var_name: value})

    def delete_value(self, var_name: str) -> None:
        """
        Deletes a local variable from the scope.

        :param var_name: The name of the local variable.
        """
        var_name = resolve_string_in_scope(var_name, self)
        if var_name in self._locals:
            del self._locals[var_name]

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
