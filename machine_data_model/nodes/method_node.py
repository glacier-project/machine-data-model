from collections.abc import Callable

from typing_extensions import override

from machine_data_model.nodes.data_model_node import DataModelNode
from machine_data_model.nodes.variable_node import VariableNode


class MethodNode(DataModelNode):
    """
    A MethodNode class is a node that represents a method in the machine data model.
    Methods of the machine data model are used to declare functions that can be executed
    on the machine data model.
    """

    def __init__(self, **kwargs):
        """
        Initialize a new MethodNode instance.
        :param kwargs: A dictionary containing the attributes of the method node. The
        dictionary may contain the following keys:
            - id: The unique identifier of the method.
            - name: The name of the method.
            - description: The description of the method.
            - parameters: A list of parameters of the method.
            - returns: A list of return values of the method.
            - callback: The function to be executed when the method is called.
        """
        super().__init__(**kwargs)
        self._parameters: list[VariableNode] = kwargs.get("parameters", [])
        self._returns: list[VariableNode] = kwargs.get("returns", [])
        self._callback: Callable = kwargs.get("callback", lambda: None)
        self._pre_call = lambda **kwargs: None
        self._post_call = lambda res: None

    @property
    def parameters(self):
        return self._parameters

    def add_parameter(self, parameter):
        """
        Add a parameter to the method.
        :param parameter: The parameter to add to the method.
        """
        self._parameters.append(parameter)

    def remove_parameter(self, parameter):
        """
        Remove a parameter from the method.
        :param parameter: The parameter to remove from the method.
        """
        if parameter not in self._parameters:
            raise ValueError(f"Parameter '{parameter}' not found in method '{self.id}'")
        self._parameters.remove(parameter)

    @property
    def returns(self):
        return self._returns

    def add_return_value(self, return_value):
        """
        Add a return value to the method.
        :param return_value: The return value to add to the method.
        """
        self._returns.append(return_value)

    def remove_return_value(self, return_value):
        """
        Remove a return value from the method.
        :param return_value: The return value to remove from the method.
        """
        if return_value not in self._returns:
            raise ValueError(
                f"Return value '{return_value}' not found in method '{self.id}'"
            )
        self._returns.remove(return_value)

    @property
    def callback(self):
        return self._callback

    @callback.setter
    def callback(self, callback):
        self._callback = callback

    @override
    def __getitem__(self, node_name: str) -> VariableNode:
        """
        Get a parameter or return value of the method by name.
        :param node_name: The name of the parameter or return value to get from the
            method.
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
        :return: True if the method has a parameter or return value with the specified
            name, False otherwise.
        """
        for parameter in self._parameters:
            if parameter.name == node_name:
                return True
        for return_value in self._returns:
            if return_value.name == node_name:
                return True
        return False

    @override
    def __iter__(self):
        """
        Iterate over the parameters and return values of the method.
        :return: An iterator over the parameters and return values of the method.
        """
        yield from self._parameters
        yield from self._returns

    def __call__(self, *args, **kwargs):
        """
        Call the method with the specified arguments.
        :param args: The positional arguments of the method.
        :param kwargs: The keyword arguments of the method.
        :return: The return values of the method.
        """
        if self._callback is None:
            raise ValueError(f"Method '{self.id}' has no callback function")

        kwargs = {**kwargs}

        for parameter in self._parameters:
            if parameter.name in kwargs:
                continue
            # add the first args to the kwargs
            if args:
                param_value = args[0]
                args = args[1:]
            else:
                param_value = parameter._read_value()
            kwargs[parameter.name] = param_value

        self._pre_call(**kwargs)
        result = {}
        res = self._callback(**kwargs)
        res = res if isinstance(res, tuple) else (res,)
        for index, return_value in enumerate(res):
            result[self._returns[index].name] = return_value
        assert len(result) == len(self._returns)
        self._post_call(result)

        return result

    def __str__(self):
        return (
            f"MethodNode("
            f"id={self.id}, "
            f"name={self.name}, "
            f"description={self.description})"
        )

    def __repr__(self):
        return self.__str__()
