"""
Method node implementations for machine data models.

This module provides method node classes that represent executable functions in
the machine data model, including synchronous and asynchronous methods with
parameter and return value handling.
"""

from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from typing import Any

from typing_extensions import override

from machine_data_model.nodes.data_model_node import DataModelNode
from machine_data_model.nodes.variable_node import VariableNode
from machine_data_model.protocols.frost_v1.frost_message import FrostMessage
from machine_data_model.tracing import trace_method_end, trace_method_start


@dataclass
class MethodExecutionResult:
    """
    Represents the result of executing or resuming a method node.

    Attributes:
        return_values:
            A dictionary of return values of the method node if the method is
            completed, otherwise it is None.
        messages:
            A list of Frost messages to be sent as a result of executing or
            resuming the method node.

    """

    return_values: dict[str, Any]
    messages: Sequence[FrostMessage] | None = None


class MethodNode(DataModelNode):
    """
    A MethodNode class is a node that represents a synchronous method in the
    machine data model. Methods of the machine data model are used to declare
    functions that can be executed on the machine data model.

    Attributes:
        _parameters (list[VariableNode]):
            A list of parameters for the method.
        _returns (list[VariableNode]):
            A list of return values for the method.
        _callback (Callable[..., Any]):
            The function to execute when the method is called.
        _pre_call (Callable[..., None]):
            The function to run before the method is called.
        _post_call (Callable[..., None]):
            The function to run after the method is called.

    """

    _parameters: list[VariableNode]
    _returns: list[VariableNode]
    _callback: Callable[..., Any]
    _pre_call: Callable[..., None]
    _post_call: Callable[..., None]

    def __init__(
        self,
        id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        parameters: list[VariableNode] | None = None,
        returns: list[VariableNode] | None = None,
        callback: Callable[..., Any] | None = None,
    ):
        """
        Initialize a new MethodNode instance.

        Args:
            id (str | None):
                The unique identifier of the method.
            name (str | None):
                The name of the method.
            description (str | None):
                The description of the method.
            parameters (list[VariableNode] | None):
                A list of parameters for the method.
            returns (list[VariableNode] | None):
                A list of return values for the method.
            callback (Callable[..., Any] | None):
                The function to execute when the method is called.

        """
        super().__init__(id=id, name=name, description=description)
        self._parameters = parameters if parameters is not None else []
        self._returns = returns if returns is not None else []
        self._callback = callback if callback is not None else lambda **kwargs: None
        self._pre_call = lambda **kwargs: None
        self._post_call = lambda res: None

        self.register_children(self._parameters)
        self.register_children(self._returns)
        for parameter in self._parameters:
            assert isinstance(
                parameter, VariableNode
            ), "Parameter must be a VariableNode"
        for return_value in self._returns:
            assert isinstance(
                return_value, VariableNode
            ), "Return value must be a VariableNode"

    @property
    def parameters(self) -> list[VariableNode]:
        """
        Returns the list of parameters for the method.

        Returns:
            list[VariableNode]:
                A list of `VariableNode` instances representing the method's
                parameters.

        """
        return self._parameters

    def add_parameter(self, parameter: VariableNode) -> None:
        """
        Add a parameter to the method.

        Args:
            parameter (VariableNode):
                The parameter to add to the method.

        """
        assert isinstance(parameter, VariableNode), "Parameter must be a VariableNode"
        self._parameters.append(parameter)
        parameter.parent = self

    def remove_parameter(self, parameter: VariableNode) -> None:
        """
        Remove a parameter from the method.

        Args:
            parameter (VariableNode):
                The parameter to remove from the method.

        Raises:
            ValueError:
                If the parameter is not found in the method.

        """
        if parameter not in self._parameters:
            raise ValueError(f"Parameter '{parameter}' not found in method '{self.id}'")
        self._parameters.remove(parameter)
        parameter.parent = None

    @property
    def returns(self) -> list[VariableNode]:
        """
        Returns the list of return values for the method.

        Returns:
            list[VariableNode]:
                A list of `VariableNode` instances representing the method's
                return values.

        """
        return self._returns

    def add_return_value(self, return_value: VariableNode) -> None:
        """
        Add a return value to the method.

        Args:
            return_value (VariableNode):
                The return value to add to the method.

        """
        assert isinstance(
            return_value, VariableNode
        ), "Return value must be a VariableNode"
        self._returns.append(return_value)
        return_value.parent = self

    def remove_return_value(self, return_value: VariableNode) -> None:
        """
        Remove a return value from the method.

        Args:
            return_value (VariableNode):
                The return value to remove from the method.

        Raises:
            ValueError:
                If the return value is not found in the method.

        """
        if return_value not in self._returns:
            raise ValueError(
                f"Return value '{return_value}' not found in method '{self.id}'"
            )
        self._returns.remove(return_value)
        return_value.parent = None

    @property
    def callback(self) -> Callable:
        """
        Gets the callback function for the method.

        Returns:
            Callable:
                The callback function.

        """
        return self._callback

    @callback.setter
    def callback(self, call: Callable) -> None:
        """
        Sets the callback function for the method.

        Args:
            call (Callable):
                The callback function to set.

        """
        self._callback = call

    @property
    def pre_callback(self) -> Callable:
        """
        Gets the pre-call function for the method.

        Returns:
            Callable:
                The pre-call function.

        """
        return self._pre_call

    @pre_callback.setter
    def pre_callback(self, pre_call: Callable) -> None:
        """
        Sets the pre-call function for the method.

        Args:
            pre_call (Callable):
                The pre-call function to set.

        """
        self._pre_call = pre_call

    @property
    def post_callback(self) -> Callable:
        """
        Gets the post-call function for the method.

        Returns:
            Callable:
                The post-call function.

        """
        return self._post_call

    @post_callback.setter
    def post_callback(self, callback: Callable) -> None:
        """
        Sets the post-call function for the method.

        Args:
            callback (Callable):
                The post-call function to set.

        """
        self._post_call = callback

    def is_async(self) -> bool:
        """
        Returns always False for synchronous methods.

        Returns:
            bool:
                False

        """
        return False

    @override
    def __getitem__(self, node_name: str) -> VariableNode:
        """
        Get a parameter or return value of the method by name.

        Args:
            node_name (str):
                The name of the parameter or return value to get from the
                method.

        Returns:
            VariableNode:
                The parameter or return value with the specified name.

        Raises:
            ValueError:
                If the node with the specified name is not found.

        """
        for parameter in self._parameters:
            if parameter.name == node_name:
                return parameter
        for return_value in self._returns:
            if return_value.name == node_name:
                return return_value
        raise ValueError(
            f"Node with name '{node_name}' not found in method '{self.id}'"
        )

    @override
    def __contains__(self, node_name: str) -> bool:
        """
        Check if the method has a parameter or return value with the specified
        name.

        Args:
            node_name (str):
                The name of the parameter or return value to check.

        Returns:
            bool:
                True if the method has a parameter or return value with the
                specified name, False otherwise.

        """
        for parameter in self._parameters:
            if parameter.name == node_name:
                return True
        for return_value in self._returns:
            if return_value.name == node_name:
                return True
        return False

    @override
    def __iter__(self) -> Iterator[VariableNode]:
        """
        Iterate over the parameters and return values of the method.

        Returns:
            Iterator[VariableNode]:
                An iterator over the parameters and return values of the method.

        """
        yield from self._parameters
        yield from self._returns

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
        if self._callback is None:
            raise ValueError(f"Method '{self.id}' has no callback function")

        kwargs = self._resolve_arguments(*args, **kwargs)

        # Trace method start
        start_time = trace_method_start(
            method_id=self.id,
            args=kwargs,
            source=self.qualified_name,
            data_model_id=self.data_model.name if self.data_model else "",
        )

        self._pre_call(**kwargs)
        ret_c = self._callback(**kwargs)
        ret = self._build_return_dict(ret_c)

        self._post_call(ret)

        # Trace method end
        trace_method_end(
            method_id=self.id,
            returns=ret,
            start_time=start_time,
            source=self.qualified_name,
            data_model_id=self.data_model.name if self.data_model else "",
        )

        return MethodExecutionResult(return_values=ret)

    def _resolve_arguments(
        self, *args: list[Any], **kwargs: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Resolves the arguments for the method. It fills in the missing arguments
        with default values or reads them from the parameters.

        Args:
            *args (list[Any]):
                The positional arguments of the method.
            **kwargs (dict[str, Any]):
                The keyword arguments of the method.

        Returns:
            dict[str, Any]:
                A dictionary of arguments for the method.

        """
        kwargs = {**kwargs}

        for parameter in self._parameters:
            if parameter.name in kwargs:
                continue
            # add the first args to the kwargs
            param_value: Any
            if args:
                param_value = args[0]
                args = args[1:]
            else:
                param_value = parameter.read()
            kwargs[parameter.name] = param_value
        return kwargs

    def _build_return_dict(self, ret: Any) -> dict[str, Any]:
        """
        Build a dictionary of return values from the method.

        Args:
            ret (Any):
                The return values of the method.

        Returns:
            dict[str, Any]:
                A dictionary of return values, where the keys are the names of
                the return values.

        """
        ret_dict = {}
        ret = ret if isinstance(ret, tuple) else (ret,)
        for index, return_value in enumerate(ret):
            ret_dict[self._returns[index].name] = return_value
        assert len(ret_dict) == len(self._returns)
        return ret_dict

    def __str__(self) -> str:
        """
        Returns a string representation of the MethodNode.

        Returns:
            str:
                A string describing the MethodNode.

        """
        return (
            f"MethodNode("
            f"id={self.id}, "
            f"name={self.name}, "
            f"description={self.description})"
        )

    def __repr__(self) -> str:
        """
        Returns a string representation of the MethodNode.

        Returns:
            str:
                The string representation of the MethodNode (same as `__str__`).

        """
        return self.__str__()

    def __eq__(self, other: object) -> bool:
        if self is other:
            return True

        if not isinstance(other, MethodNode):
            return False

        if not self._eq_base(other):
            return False

        return self._parameters == other._parameters and self._returns == other._returns


class AsyncMethodNode(MethodNode):
    """
    An AsyncMethodNode class is a node that represents an asynchronous method in
    the machine data model. Asynchronous methods of the machine data model are
    used to declare functions whose return values are not immediately available.
    Instead, the result is obtained asynchronously, typically through variable
    monitoring or event-based mechanisms.
    """

    def __init__(
        self,
        id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        parameters: list[VariableNode] | None = None,
        returns: list[VariableNode] | None = None,
        callback: Callable[..., Any] | None = None,
    ):
        """
        Initialize a new AsyncMethodNode instance.

        Args:
            id (str | None):
                The unique identifier of the method.
            name (str | None):
                The name of the method.
            description (str | None):
                The description of the method.
            parameters (list[VariableNode] | None):
                A list of parameters for the method.
            returns (list[VariableNode] | None):
                A list of return values for the method.
            callback (Callable[..., Any] | None):
                The function to execute when the method is called.

        """
        super().__init__(
            id=id,
            name=name,
            description=description,
            parameters=parameters,
            returns=returns,
            callback=callback,
        )

    def is_async(self) -> bool:
        """
        Returns always True for asynchronous methods.

        Returns:
            bool:
                True

        """
        return True

    def __str__(self) -> str:
        return f"AsyncMethodNode(id={self.id}, name={self.name}, description={self.description})"
