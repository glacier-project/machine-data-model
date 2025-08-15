from collections.abc import Callable
from typing import Any, Iterator

from typing_extensions import override

from machine_data_model.nodes.connectors.abstract_connector import AbstractConnector
from machine_data_model.nodes.data_model_node import DataModelNode
from machine_data_model.nodes.variable_node import VariableNode


class MethodNode(DataModelNode):
    """
    A MethodNode class is a node that represents a synchronous method in the machine data model.
    Methods of the machine data model are used to declare functions that can be executed
    on the machine data model.

    :ivar _parameters: A list of parameters for the method.
    :ivar _returns: A list of return values for the method.
    :ivar _callback: The function to execute when the method is called.
    :ivar _pre_call: The function to run before the method is called.
    :ivar _post_call: The function to run after the method is called.
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
        Initialize a new MethodNode instance.

        :param id: The unique identifier of the method.
        :param name: The name of the method.
        :param description: The description of the method.
        :param parameters: A list of parameters for the method.
        :param returns: A list of return values for the method.
        :param callback: The function to execute when the method is called.
        """
        super().__init__(id=id, name=name, description=description)
        self._parameters: list[VariableNode] = (
            parameters if parameters is not None else []
        )
        for parameter in self._parameters:
            assert isinstance(
                parameter, VariableNode
            ), "Parameter must be a VariableNode"
        self._returns: list[VariableNode] = returns if returns is not None else []
        for return_value in self._returns:
            assert isinstance(
                return_value, VariableNode
            ), "Return value must be a VariableNode"

        self.register_children(self._parameters)
        self.register_children(self._returns)

        self._callback: Callable[..., Any] = (
            callback if callback is not None else lambda **kwargs: None
        )
        self._pre_call: Callable[..., None] = lambda **kwargs: None
        self._post_call: Callable[..., None] = lambda res: None

    @property
    def parameters(self) -> list[VariableNode]:
        """
        Returns the list of parameters for the method.

        :return: A list of `VariableNode` instances representing the method's parameters.
        """
        return self._parameters

    def add_parameter(self, parameter: VariableNode) -> None:
        """
        Add a parameter to the method.

        :param parameter: The parameter to add to the method.
        """
        assert isinstance(parameter, VariableNode), "Parameter must be a VariableNode"
        self._parameters.append(parameter)
        parameter.parent = self

    def remove_parameter(self, parameter: VariableNode) -> None:
        """
        Remove a parameter from the method.

        :param parameter: The parameter to remove from the method.
        """
        if parameter not in self._parameters:
            raise ValueError(f"Parameter '{parameter}' not found in method '{self.id}'")
        self._parameters.remove(parameter)
        parameter.parent = None

    @property
    def returns(self) -> list[VariableNode]:
        """
        Returns the list of return values for the method.

        :return: A list of `VariableNode` instances representing the method's return values.
        """
        return self._returns

    def add_return_value(self, return_value: VariableNode) -> None:
        """
        Add a return value to the method.

        :param return_value: The return value to add to the method.
        """
        assert isinstance(
            return_value, VariableNode
        ), "Return value must be a VariableNode"
        self._returns.append(return_value)
        return_value.parent = self

    def remove_return_value(self, return_value: VariableNode) -> None:
        """
        Remove a return value from the method.

        :param return_value: The return value to remove from the method.
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

        :return: The callback function.
        """
        return self._callback

    @callback.setter
    def callback(self, call: Callable) -> None:
        """
        Sets the callback function for the method.

        :param call: The callback function to set.
        """
        self._callback = call

    @property
    def pre_callback(self) -> Callable:
        """
        Gets the pre-call function for the method.

        :return: The pre-call function.
        """
        return self._pre_call

    @pre_callback.setter
    def pre_callback(self, pre_call: Callable) -> None:
        """
        Sets the pre-call function for the method.

        :param pre_call: The pre-call function to set.
        """
        self._pre_call = pre_call

    @property
    def post_callback(self) -> Callable:
        """
        Gets the post-call function for the method.

        :return: The post-call function.
        """
        return self._post_call

    @post_callback.setter
    def post_callback(self, callback: Callable) -> None:
        """
        Sets the post-call function for the method.

        :param callback: The post-call function to set.
        """
        self._post_call = callback

    def is_async(self) -> bool:
        """
        Returns always False for synchronous methods.

        :return: False
        """
        return False

    @override
    def __getitem__(self, node_name: str) -> VariableNode:
        """
        Get a parameter or return value of the method by name.

        :param node_name: The name of the parameter or return value to get from the method.
        :return: The parameter or return value with the specified name.
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
        Check if the method has a parameter or return value with the specified name.

        :param node_name: The name of the parameter or return value to check.
        :return: True if the method has a parameter or return value with the specified name, False otherwise.
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

        :return: An iterator over the parameters and return values of the method.
        """
        yield from self._parameters
        yield from self._returns

    def __call__(self, *args: list[Any], **kwargs: dict[str, Any]) -> dict[str, Any]:
        """
        Call the method with the specified arguments.

        :param args: The positional arguments of the method.
        :param kwargs: The keyword arguments of the method.
        :return: The return values of the method.
        """
        if self._callback is None:
            raise ValueError(f"Method '{self.id}' has no callback function")

        kwargs = self._resolve_arguments(*args, **kwargs)

        self._pre_call(**kwargs)
        if self.is_remote():
            assert isinstance(
                self.connector, AbstractConnector
            ), "connector must be an AbstractConnector"
            assert (
                self.remote_path is not None
            ), "remote_path must be set for a remote node"
            ret_c = self.connector.call_node_as_method(self.remote_path, kwargs)
        else:
            ret_c = self._callback(**kwargs)
        ret = self._build_return_dict(ret_c)

        self._post_call(ret)

        return ret

    def _resolve_arguments(
        self, *args: list[Any], **kwargs: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Resolves the arguments for the method. It fills in the missing arguments with
        default values or reads them from the parameters.

        :param args: The positional arguments of the method.
        :param kwargs: The keyword arguments of the method.
        :return: A dictionary of arguments for the method.
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

        :param ret: The return values of the method.
        :return: A dictionary of return values, where the keys are the names of the return values.
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

        :return: A string describing the MethodNode.
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

        :return: The string representation of the MethodNode (same as `__str__`).
        """
        return self.__str__()


class AsyncMethodNode(MethodNode):
    """
    An AsyncMethodNode class is a node that represents an asynchronous method in the
    machine data model. Asynchronous methods of the machine data model are used to
    declare functions whose return values are not immediately available. Instead,
    the result is obtained asynchronously, typically through variable monitoring or
    event-based mechanisms.

    :ivar _parameters: A list of parameters for the method.
    :ivar _returns: A list of return values for the method.
    :ivar _callback: The function to execute when the method is called.
    :ivar _pre_call: The function to run before the method is called.
    :ivar _post_call: The function to run after the method is called.
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

        :param id: The unique identifier of the method.
        :param name: The name of the method.
        :param description: The description of the method.
        :param parameters: A list of parameters for the method.
        :param returns: A list of return values for the method.
        :param callback: The function to execute when the method is called.
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

        :return: True
        """
        return True

    def __str__(self) -> str:
        return f"AsyncMethodNode(id={self.id}, name={self.name}, description={self.description})"
