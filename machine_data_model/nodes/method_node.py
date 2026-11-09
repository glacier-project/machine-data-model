"""Method node implementations for machine data models.

This module provides method node classes that represent executable functions in
the machine data model, including synchronous and asynchronous methods with
parameter and return value handling.
"""

from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from typing_extensions import override

from machine_data_model.behavior.condition import (
    Condition,
    ConditionError,
    ConditionOutcome,
    ConditionResult,
)
from machine_data_model.behavior.execution_context import (
    ExecutionContext,
    template_re,
)
from machine_data_model.behavior.execution_error import (
    ExecutionError,
    ExecutionErrorCode,
    sanitize_detail,
)
from machine_data_model.nodes.connectors.abstract_connector import (
    AbstractConnector,
)
from machine_data_model.nodes.connectors.abstract_remote_resource_spec import (
    AbstractRemoteResourceSpec,
)
from machine_data_model.nodes.data_model_node import (
    DataModelNode,
)
from machine_data_model.nodes.variable_node import VariableNode
from machine_data_model.protocols.frost_v1.frost_message import FrostMessage
from machine_data_model.tracing import trace_method_end, trace_method_start


@dataclass
class MethodExecutionResult:
    """Represents the result of executing or resuming a method node.

    Attributes:
        return_values:
            A dictionary of return values of the method node if the method is
            completed, otherwise it is None.
        messages:
            A list of Frost messages to be sent as a result of executing or
            resuming the method node.

    Error:
            The reason of the failure if the execution ended in error,
            otherwise None. When set, `return_values` is empty.

    """

    return_values: dict[str, Any]
    messages: Sequence[FrostMessage] | None = None
    error: ExecutionError | None = None


# Longest condition text and observed text kept in a requires error message.
_MAX_REQUIRES_TEXT = 256

# Most unmet conditions named in the message of a rejection; the others are
# counted. The list in `MethodPreconditionError.outcomes` is complete.
_MAX_LISTED_CONDITIONS = 5

# Longest list of unmet conditions in the message, in characters.
_MAX_REQUIRES_MESSAGE = 512


class MethodPreconditionError(Exception):
    """Raised when a method is called while its `requires` are not satisfied.

    Attributes:
        error (ExecutionError):
            The reason of the rejection: `PRECONDITION_NOT_MET`, `NO_DATA` or
            `INVALID_CONFIGURATION`.
        outcomes (list[ConditionOutcome]):
            The outcome of every condition that was evaluated.
        variables (tuple[VariableNode, ...]):
            The variables the conditions read, each once, resolved by the same
            attempt that produced the error. A caller that wants to wait for
            them to change subscribes to these, without resolving the paths a
            second time. Empty for `INVALID_CONFIGURATION`: a misconfigured
            condition is never waited on.

    """

    def __init__(
        self,
        error: ExecutionError,
        outcomes: list[ConditionOutcome],
        variables: Sequence[VariableNode] = (),
    ) -> None:
        """Initialize a new MethodPreconditionError.

        Args:
            error (ExecutionError):
                The reason of the rejection.
            outcomes (list[ConditionOutcome]):
                The outcome of every condition that was evaluated.
            variables (Sequence[VariableNode]):
                The variables the conditions read.

        """
        super().__init__(error.message)
        self.error = error
        self.outcomes = outcomes
        self.variables = tuple(variables)


class MethodNode(DataModelNode):
    """Represent a synchronous method in the machine data model.

    Methods of the machine data model are used to declare functions that can be
    executed on the machine data model.

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
        _requires (tuple[Condition, ...]):
            The conditions on variables of the data model that must all hold
            for the method to be called.

    """

    _parameters: list[VariableNode]
    _returns: list[VariableNode]
    _callback: Callable[..., Any]
    _pre_call: Callable[..., None]
    _post_call: Callable[..., None]
    _requires: tuple[Condition, ...]

    def __init__(
        self,
        id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        parameters: list[VariableNode] | None = None,
        returns: list[VariableNode] | None = None,
        callback: Callable[..., Any] | None = None,
        connector_name: str | None = None,
        remote_resource_spec: AbstractRemoteResourceSpec | None = None,
        requires: Sequence[Condition] | None = None,
    ):
        """Initialize a new MethodNode instance.

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
            connector_name (str | None):
                The connector's name/identifier if this node is a remote node.
                Used to interact with the remote server to read/write the
                variable.
            remote_resource_spec (AbstractRemoteResourceSpec | None):
                Protocol-specific properties for remote nodes.
            requires (Sequence[Condition] | None):
                Conditions on variables that must all hold for the method to
                be called. A condition can use `${name}` for a parameter of
                the method.
        """
        super().__init__(
            id=id,
            name=name,
            description=description,
            connector_name=connector_name,
            remote_resource_spec=remote_resource_spec,
        )
        self._requires = tuple(requires) if requires is not None else ()
        self._parameters = parameters if parameters is not None else []
        self._returns = returns if returns is not None else []
        self._callback = (
            callback if callback is not None else lambda **kwargs: None
        )
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
        self._validate_requires_templates()

    def _validate_requires_templates(self) -> None:
        """Check that every `${name}` in `requires` is a parameter.

        Raises:
            ValueError:
                If a condition refers to a name that is not a parameter of the
                method: the call could never provide it.

        """
        names = {parameter.name for parameter in self._parameters}
        for condition in self._requires:
            texts = [condition.variable]
            if isinstance(condition.rhs, str):
                texts.append(condition.rhs)
            for text in texts:
                for name in template_re.findall(text):
                    if name not in names:
                        raise ValueError(
                            f"requires of method '{self.name}': "
                            f"'${{{name}}}' in '{condition.variable} "
                            f"{condition.operator.value} {condition.rhs}' is "
                            f"not a parameter of the method"
                        )

    @property
    def parameters(self) -> list[VariableNode]:
        """Returns the list of parameters for the method.

        Returns:
            list[VariableNode]:
                A list of `VariableNode` instances representing the method's
                parameters.

        """
        return self._parameters

    @property
    def requires(self) -> tuple[Condition, ...]:
        """Returns the conditions that must hold for the method to be called.

        A tuple, so that the conditions cannot be changed from outside after
        the construction check (every `${name}` is a parameter) ran.

        Returns:
            tuple[Condition, ...]:
                The conditions, combined with AND. Empty if the method has no
                preconditions.

        """
        return self._requires

    def add_parameter(self, parameter: VariableNode) -> None:
        """Add a parameter to the method.

        Args:
            parameter (VariableNode):
                The parameter to add to the method.

        """
        assert isinstance(
            parameter, VariableNode
        ), "Parameter must be a VariableNode"
        self._parameters.append(parameter)
        parameter.parent = self

    def remove_parameter(self, parameter: VariableNode) -> None:
        """Remove a parameter from the method.

        Args:
            parameter (VariableNode):
                The parameter to remove from the method.

        Raises:
            ValueError:
                If the parameter is not found in the method.

        """
        if parameter not in self._parameters:
            raise ValueError(
                f"Parameter '{parameter}' not found in method '{self.id}'"
            )
        self._parameters.remove(parameter)
        parameter.parent = None

    @property
    def returns(self) -> list[VariableNode]:
        """Returns the list of return values for the method.

        Returns:
            list[VariableNode]:
                A list of `VariableNode` instances representing the method's
                return values.

        """
        return self._returns

    def add_return_value(self, return_value: VariableNode) -> None:
        """Add a return value to the method.

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
        """Remove a return value from the method.

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
        """Gets the callback function for the method.

        Returns:
            Callable:
                The callback function.

        """
        return self._callback

    @callback.setter
    def callback(self, call: Callable) -> None:
        """Sets the callback function for the method.

        Args:
            call (Callable):
                The callback function to set.

        """
        self._callback = call

    @property
    def pre_callback(self) -> Callable:
        """Gets the pre-call function for the method.

        Returns:
            Callable:
                The pre-call function.

        """
        return self._pre_call

    @pre_callback.setter
    def pre_callback(self, pre_call: Callable) -> None:
        """Sets the pre-call function for the method.

        Args:
            pre_call (Callable):
                The pre-call function to set.

        """
        self._pre_call = pre_call

    @property
    def post_callback(self) -> Callable:
        """Gets the post-call function for the method.

        Returns:
            Callable:
                The post-call function.

        """
        return self._post_call

    @post_callback.setter
    def post_callback(self, callback: Callable) -> None:
        """Sets the post-call function for the method.

        Args:
            callback (Callable):
                The post-call function to set.

        """
        self._post_call = callback

    def is_async(self) -> bool:
        """Returns always False for synchronous methods.

        Returns:
            bool:
                False

        """
        return False

    @override
    def __getitem__(self, node_name: str) -> VariableNode:
        """Get a parameter or return value of the method by name.

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
        """Check if the method has the specified parameter or return value.

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
        """Iterate over the parameters and return values of the method.

        Returns:
            Iterator[VariableNode]:
                An iterator over the parameters and return values of the method.

        """
        yield from self._parameters
        yield from self._returns

    def __call__(self, *args: Any, **kwargs: Any) -> MethodExecutionResult:
        """Call the method with the specified arguments.

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

        # Reject the call before anything is traced or run.
        self._check_requires(kwargs)

        # Trace method start
        start_time = trace_method_start(
            method_id=self.id,
            args=kwargs,
            source=self.qualified_name,
            data_model_id=self.data_model.name if self.data_model else "",
        )

        self._pre_call(**kwargs)
        if self.is_remote():
            connector = self.connector
            if not isinstance(connector, AbstractConnector):
                raise RuntimeError("Remote methods must have a valid connector")
            ret_c = connector.call_node_as_method(self.remote_resource, kwargs)
        else:
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

    def _requires_scope(
        self, kwargs: dict[str, Any]
    ) -> tuple[ExecutionContext, Callable[[str], DataModelNode | None]]:
        """Build what a condition of `requires` is evaluated with.

        Args:
            kwargs (dict[str, Any]):
                The resolved arguments of the call.

        Returns:
            tuple[ExecutionContext, Callable[[str], DataModelNode | None]]:
                A throwaway context holding the arguments (set with
                `set_all_values`, so a parameter called `context_id` does not
                collide; it is registered nowhere) and the function that
                resolves a path in the data model of the method.

        """
        scope = ExecutionContext("requires")
        scope.set_all_values(**kwargs)
        data_model = self.data_model

        def resolve_node(path: str) -> DataModelNode | None:
            return data_model.get_node(path) if data_model else None

        return scope, resolve_node

    def evaluate_requires(self, **kwargs: Any) -> list[ConditionOutcome]:
        """Evaluate the `requires` without calling the method.

        A diagnostic helper: it calls neither the callback nor the pre and post
        callbacks, traces nothing and changes no variable.

        Args:
            **kwargs (Any):
                The arguments of the call. A parameter that is not given takes
                the value of the parameter node.

        Returns:
            list[ConditionOutcome]:
                The outcome of every condition, in order.

        Raises:
            ConditionError:
                If a condition is misconfigured (unknown variable, not a
                variable, remote without a connector).
            KeyError:
                If a condition uses a name that is not in the arguments.

        """
        resolved = self._resolve_arguments(**kwargs)
        scope, resolve_node = self._requires_scope(resolved)
        return [
            condition.evaluate(resolve_node, scope)
            for condition in self._requires
        ]

    def is_executable(self, **kwargs: Any) -> bool:
        """Tell whether a call with these arguments would pass `requires`.

        Args:
            **kwargs (Any):
                The arguments of the call. A parameter that is not given takes
                the value of the parameter node.

        Returns:
            bool:
                True only if every condition holds. False if one does not hold,
                has no data or is misconfigured. The callbacks are not called.

        """
        try:
            outcomes = self.evaluate_requires(**kwargs)
        except (ConditionError, KeyError):
            return False
        return all(o.result is ConditionResult.OK for o in outcomes)

    def _check_requires(self, kwargs: dict[str, Any]) -> None:
        """Raise if the `requires` of the method are not satisfied.

        Conditions are evaluated with cached values, in a scope made of the
        arguments of the call. Every condition is evaluated so that the error
        lists all that are unmet, except that a misconfigured condition stops
        the check at once.

        Args:
            kwargs (dict[str, Any]):
                The resolved arguments of the call.

        Raises:
            MethodPreconditionError:
                If a condition does not hold (`PRECONDITION_NOT_MET`), cannot
                be evaluated for lack of data (`NO_DATA`) or is misconfigured
                (`INVALID_CONFIGURATION`). This is the only exception raised
                for a requires problem.

        """
        if not self._requires:
            return
        scope, resolve_node = self._requires_scope(kwargs)

        outcomes: list[ConditionOutcome] = []
        variables: list[VariableNode] = []
        for condition in self._requires:
            try:
                # Resolve once: the same result feeds the evaluation and the
                # variables a caller may subscribe to.
                resolved = condition.resolve(resolve_node, scope)
                outcomes.append(
                    condition.evaluate_on(
                        resolved.variable, resolved.rhs, path=resolved.path
                    )
                )
                if not any(resolved.variable is v for v in variables):
                    variables.append(resolved.variable)
            except ConditionError as exp:
                raise MethodPreconditionError(
                    self._invalid_requires(condition, exp.message), outcomes
                ) from exp
            except KeyError as exp:
                name = exp.args[0] if exp.args else "?"
                raise MethodPreconditionError(
                    self._invalid_requires(
                        condition, f"unknown value '{name}' in the call"
                    ),
                    outcomes,
                ) from exp

        failed = [o for o in outcomes if o.result is ConditionResult.FAILED]
        no_data = [o for o in outcomes if o.result is ConditionResult.NO_DATA]
        if not failed and not no_data:
            return
        code = (
            ExecutionErrorCode.PRECONDITION_NOT_MET
            if failed
            else ExecutionErrorCode.NO_DATA
        )
        unmet = failed + no_data
        observed = "; ".join(
            f"{o.variable} = {o.observed}" for o in unmet if o.observed
        )
        listed = "; ".join(o.message for o in unmet[:_MAX_LISTED_CONDITIONS])
        if len(unmet) > _MAX_LISTED_CONDITIONS:
            listed += f" (+{len(unmet) - _MAX_LISTED_CONDITIONS} more)"
        raise MethodPreconditionError(
            ExecutionError(
                code,
                f"method '{self.qualified_name}' requires not met: "
                + sanitize_detail(listed, _MAX_REQUIRES_MESSAGE),
                node=self.qualified_name,
                observed=sanitize_detail(observed, _MAX_REQUIRES_TEXT)
                if observed
                else None,
            ),
            outcomes,
            variables,
        )

    def _invalid_requires(
        self, condition: Condition, problem: str
    ) -> ExecutionError:
        """Build the error of a condition that cannot be evaluated.

        Args:
            condition (Condition):
                The misconfigured condition.
            problem (str):
                What is wrong with it.

        Returns:
            ExecutionError:
                An `INVALID_CONFIGURATION` error naming the method, the
                condition and the problem.

        """
        text = sanitize_detail(
            f"{condition.variable} {condition.operator.value} "
            f"{condition.rhs}",
            _MAX_REQUIRES_TEXT,
        )
        return ExecutionError(
            ExecutionErrorCode.INVALID_CONFIGURATION,
            f"method '{self.qualified_name}' has an invalid requires "
            f"'{text}': {sanitize_detail(problem, _MAX_REQUIRES_TEXT)}",
            node=self.qualified_name,
        )

    def _resolve_arguments(
        self, *args: list[Any], **kwargs: dict[str, Any]
    ) -> dict[str, Any]:
        """Resolve the arguments for the method call.

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
        """Build a dictionary of return values from the method.

        Args:
            ret (Any):
                The return values of the method.

        Returns:
            dict[str, Any]:
                A dictionary of return values, where the keys are the names of
                the return values.

        """
        ret_dict = {}
        assert not isinstance(ret, Mapping), "Return value cannot be a mapping."
        f" Received {ret} of type {type(ret)}."
        ret = ret if isinstance(ret, list | tuple) else (ret,)
        for index, return_value in enumerate(ret):
            ret_dict[self._returns[index].name] = return_value
        assert len(ret_dict) == len(self._returns), f"{ret_dict}"
        return ret_dict

    def __str__(self) -> str:
        """Returns a string representation of the MethodNode.

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
        """Returns a string representation of the MethodNode.

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

        return (
            self._parameters == other._parameters
            and self._returns == other._returns
            and self._requires == other._requires
        )


class AsyncMethodNode(MethodNode):
    """Represent an asynchronous method in the machine data model.

    Asynchronous methods of the machine data model are used to declare functions
    whose return values are not immediately available. Instead, the result is
    obtained asynchronously, typically through variable monitoring or
    event-based mechanisms.
    """

    def __init__(
        self,
        id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        parameters: list[VariableNode] | None = None,
        returns: list[VariableNode] | None = None,
        callback: Callable[..., Any] | None = None,
        connector_name: str | None = None,
        remote_resource_spec: AbstractRemoteResourceSpec | None = None,
        requires: Sequence[Condition] | None = None,
    ):
        """Initialize a new AsyncMethodNode instance.

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
            connector_name (str | None):
                The connector's name/identifier if this node is a remote node.
                Used to interact with the remote server to read/write the
                variable.
            remote_resource_spec (AbstractRemoteResourceSpec | None):
                Protocol-specific properties for remote nodes.
            requires (Sequence[Condition] | None):
                Conditions on variables that must all hold for the method to
                be called. A condition can use `${name}` for a parameter of
                the method.
        """
        super().__init__(
            id=id,
            name=name,
            description=description,
            parameters=parameters,
            returns=returns,
            callback=callback,
            connector_name=connector_name,
            remote_resource_spec=remote_resource_spec,
            requires=requires,
        )

    def is_async(self) -> bool:
        """Returns always True for asynchronous methods.

        Returns:
            bool:
                True

        """
        return True

    def __str__(self) -> str:
        return (
            f"AsyncMethodNode(id={self.id}, "
            f"name={self.name}, "
            f"description={self.description})"
        )
