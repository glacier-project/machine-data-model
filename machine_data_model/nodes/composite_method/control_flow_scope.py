from typing import Any


class ControlFlowScope:
    """
    Execution scope for a control flow graph. It contains the local variables and the program counter
    of the control flow graph execution.

    :ivar _scope_id: The unique identifier of the scope.
    :ivar _locals: The local variables of the scope.
    :ivar _pc: The program counter of the scope.
    :ivar _is_active: A flag indicating if the scope is active or not.
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
        self._is_active = True
        self.set_all_values(**kwargs)

    def set_all_values(self, **kwargs: dict[str, Any]) -> None:
        """
        Sets the values of the local variables in the scope.

        :param kwargs: The local variables to set in the scope.
        """
        if not self._is_active:
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
        before = string.split("${")[0]
        after = string.split("}")[-1]
        result = string.split("${")[-1]
        result = result.split("}")[0]
        assert self._locals[
            result
        ], f"Variable '{result}' not found in scope {self._locals[result]}"
        result = str(self._locals[result][0])
        return before + result + after

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
        self._is_active = False

    def is_active(self) -> bool:
        """
        Check if the scope is active.

        :return: True if the scope is active, False otherwise.
        """
        return self._is_active

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
        return f"ControlFlowScope(execution_id={self._scope_id}, pc={self._pc})"
