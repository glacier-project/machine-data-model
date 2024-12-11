from typing import Callable, List, Union

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
            - return: A list of return values of the method.
            - callback: The function to be executed when the method is called.
        """
        super().__init__(**kwargs)
        self._parameters: List[VariableNode] = kwargs.get("parameters", [])
        self._return: List[VariableNode] = kwargs.get("return", [])
        self._callback: Union[Callable, None] = kwargs.get("callback", None)

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
    def return_values(self):
        return self._return

    def add_return_value(self, return_value):
        """
        Add a return value to the method.
        :param return_value: The return value to add to the method.
        """
        self._return.append(return_value)

    def remove_return_value(self, return_value):
        """
        Remove a return value from the method.
        :param return_value: The return value to remove from the method.
        """
        if return_value not in self._return:
            raise ValueError(
                f"Return value '{return_value}' not found in method '{self.id}'"
            )
        self._return.remove(return_value)

    @property
    def callback(self):
        return self._callback

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
                param_value = parameter.read_value()
            kwargs[parameter.name] = param_value

        return self._callback(*args, **kwargs)
