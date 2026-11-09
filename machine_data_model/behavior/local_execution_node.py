"""Local execution nodes for control flow graphs.

This module defines various node types that execute operations locally within
the control flow graph, including variable read/write, method calls, and wait
conditions.
"""

from collections.abc import Callable
from enum import Enum
import math
import time
from typing import Any

from machine_data_model.behavior.condition import (
    WaitConditionOperator,
    compare,
    get_condition_operator,
)
from machine_data_model.behavior.control_flow_node import (
    ControlFlowNode,
    ExecutionNodeResult,
    execution_error,
    execution_failure,
    execution_success,
)
from machine_data_model.behavior.execution_context import (
    ExecutionContext,
    contains_template_variables,
    resolve_string_in_context,
    resolve_value,
)
from machine_data_model.behavior.execution_error import (
    ExecutionError,
    ExecutionErrorCode,
    sanitize_detail,
)
from machine_data_model.nodes.data_model_node import DataModelNode
from machine_data_model.nodes.method_node import (
    MethodNode,
    MethodPreconditionError,
)
from machine_data_model.nodes.subscription.variable_subscription import (
    VariableSubscription,
)
from machine_data_model.nodes.variable_node import VariableNode
from machine_data_model.protocols.frost_v1.frost_message import FrostMessage
from machine_data_model.tracing import trace_wait_end, trace_wait_start
from machine_data_model.tracing.events import trace_control_flow_step

# Most times a call is tried again in one step because the values changed
# between the check that rejected it and the subscription.
_MAX_WAIT_CYCLES = 5

# Longest message of a `TIMEOUT` error, in characters.
_MAX_TIMEOUT_MESSAGE = 768

__all__ = [
    "CallMethodNode",
    "LocalExecutionNode",
    "OnUnmet",
    "ReadVariableNode",
    "WaitConditionNode",
    "WaitConditionOperator",
    "WriteVariableNode",
    "get_condition_operator",
]


class OnUnmet(str, Enum):
    """What a `CallMethodNode` does when the callee rejects the call.

    Attributes:
        WAIT:
            Keep the node running and try again when a variable that the
            `requires` of the callee read changes.
        FAIL:
            Fail the node with the error of the callee.

    """

    WAIT = "wait"
    FAIL = "fail"


class LocalExecutionNode(ControlFlowNode):
    """Local execution node in the control flow graph.

    A control flow action node is a basic unit of the control flow graph that
    can be executed locally in the context of a control flow context.

    Attributes:
        _ref_node (DataModelNode | None):
            The reference to the node in the machine data model.
        get_data_model_node (Callable[[str], DataModelNode | None] | None):
            A callable that takes a node identifier and returns the
            corresponding node in the machine data model.

    """

    _ref_node: DataModelNode | None
    get_data_model_node: Callable[[str], DataModelNode | None] | None

    def __init__(
        self,
        node: str,
        successors: list["ControlFlowNode"] | None = None,
    ):
        """Initialize a new LocalExecutionNode instance.

        Args:
            node (str):
                The identifier of a local node in the machine data model.
            successors (list["ControlFlowNode"] | None):
                A list of control flow nodes that are successors of the current
                node.

        """
        super().__init__(node=node, successors=successors)

        self._ref_node: DataModelNode | None = None
        self.get_data_model_node: (
            Callable[[str], DataModelNode | None] | None
        ) = None

    def get_successors(self) -> list["ControlFlowNode"]:
        """Return the successors of the current node.

        Returns:
            list["ControlFlowNode"]:
                The list of control flow nodes that are successors of the
                current node.

        """
        return self._successors

    def is_node_static(self) -> bool:
        """Check if the node is static.

        This is used to determine if the reference node can be resolved at
        creation time or if it needs to be resolved at execution time.

        Returns:
            bool:
                True if the node is static, otherwise False.

        """
        if len(self.node) == 0:
            return False
        return not contains_template_variables(self.node)

    def set_ref_node(self, ref_node: DataModelNode) -> None:
        """Set the reference to the node in the machine data model.

        Args:
            ref_node (DataModelNode):
                The reference to the node in the machine data model.

        """
        assert ref_node.name == self.node.split("/")[-1]
        self._ref_node = ref_node

    def get_ref_node(self) -> DataModelNode | None:
        """Get the reference to the node in the machine data model.

        Returns:
            DataModelNode | None:
                The reference to the node in the machine data model.

        """
        return self._ref_node

    def _get_ref_node(self, context: ExecutionContext) -> DataModelNode | None:
        """Get the node referenced by the current node.

        If the node is static, it returns the reference node. Otherwise, it
        resolves the value of the node in the context and retrieves the
        reference node from the machine data model.

        Args:
            context (ExecutionContext):
                The context of the control flow graph.

        Returns:
            DataModelNode | None:
                The node referenced by the current node.

        """
        if self.is_node_static() and self._ref_node is not None:
            return self._ref_node
        node_path = resolve_string_in_context(self.node, context)

        assert self.get_data_model_node is not None
        x = self.get_data_model_node(node_path)
        assert x is not None, f"Invalid node path: {node_path}"
        return x

    def __eq__(self, other: object) -> bool:
        """Check equality with another object.

        Args:
            other (object):
                The object to compare with.

        Returns:
            bool:
                True if the objects are equal, False otherwise.

        """
        if self is other:
            return True

        if not isinstance(other, LocalExecutionNode):
            return False

        return super().__eq__(other)


class ReadVariableNode(LocalExecutionNode):
    """Represents the read operation of a variable in the machine data model.

    When executed, it reads the value of the variable and stores it in the
    context.

    Attributes:
        store_as (str):
            The name of the variable used to store the value in the context.

    """

    store_as: str

    def __init__(
        self,
        variable_node: str,
        store_as: str = "",
        successors: list["ControlFlowNode"] | None = None,
    ):
        """Initialize a new ReadVariableNode instance.

        Args:
            variable_node (str):
                The identifier of the variable node in the machine data model.
            store_as (str):
                The name of the variable used to store the value in the context.
                If not specified, the value is stored with the name of the
                variable node.
            successors (list["ControlFlowNode"] | None):
                A list of control flow nodes that are successors of the current
                node.

        """
        super().__init__(node=variable_node, successors=successors)
        self.store_as = store_as

    def execute(self, context: ExecutionContext) -> ExecutionNodeResult:
        """Execute the read operation of the variable in the machine data model.

        Args:
            context (ExecutionContext):
                The context of the control flow graph.

        Returns:
            ExecutionNodeResult:
                An ExecutionNodeResult indicating success.

        """
        ref_variable = self._get_ref_node(context)
        assert isinstance(
            ref_variable, VariableNode
        ), f"Node {ref_variable} is not a VariableNode"

        # Trace the control flow step.
        trace_control_flow_step(
            node_id=self.node,
            node_type=type(self).__name__,
            execution_result=True,
            program_counter=context.get_pc(),
            source=context.id(),
            data_model_id=(
                ref_variable.data_model.name if ref_variable.data_model else ""
            ),
        )

        value = ref_variable.read()
        name = self.store_as if self.store_as else ref_variable.name
        context.set_value(name, value)
        return execution_success()

    def __eq__(self, other: object) -> bool:
        """Check equality with another object.

        Args:
            other (object):
                The object to compare with.

        Returns:
            bool:
                True if the objects are equal, False otherwise.

        """
        if self is other:
            return True

        if not isinstance(other, ReadVariableNode):
            return False

        return super().__eq__(other) and self.store_as == other.store_as


class WriteVariableNode(LocalExecutionNode):
    """Represents the write operation of a variable in the machine data model.

    When executed, it writes the value to the variable in the machine data
    model.

    Attributes:
        _value (Any):
            The value to write to the variable.

    """

    _value: Any

    def __init__(
        self,
        variable_node: str,
        value: Any,
        successors: list["ControlFlowNode"] | None = None,
    ):
        """Initialize a new WriteVariableNode instance.

        Args:
            variable_node (str):
                The identifier of the variable node in the machine data model.
            value (Any):
                The value to write to the variable. It can be a constant value
                or reference to a variable in the context.
            successors (list["ControlFlowNode"] | None):
                A list of control flow nodes that are successors of the current
                node.

        """
        super().__init__(node=variable_node, successors=successors)
        self._value = value

    @property
    def value(self) -> Any:
        """Get the value to write to the variable.

        Returns:
            Any:
                The value to write to the variable.

        """
        return self._value

    def execute(self, context: ExecutionContext) -> ExecutionNodeResult:
        """Write the value to the variable in the machine data model.

        Args:
            context (ExecutionContext):
                The context of the control flow graph.

        Returns:
            ExecutionNodeResult:
                An ExecutionNodeResult indicating success.

        """
        ref_variable = self._get_ref_node(context)
        assert isinstance(ref_variable, VariableNode)

        # Trace the control flow step.
        trace_control_flow_step(
            node_id=self.node,
            node_type=type(self).__name__,
            execution_result=True,
            program_counter=context.get_pc(),
            source=context.id(),
            data_model_id=(
                ref_variable.data_model.name if ref_variable.data_model else ""
            ),
        )

        value = resolve_value(self._value, context)
        ref_variable.write(value)
        return execution_success()

    def __eq__(self, other: object) -> bool:
        """Check equality with another object.

        Args:
            other (object):
                The object to compare with.

        Returns:
            bool:
                True if the objects are equal, False otherwise.

        """
        if self is other:
            return True

        if not isinstance(other, WriteVariableNode):
            return False

        return super().__eq__(other) and self.value == other.value


class CallMethodNode(LocalExecutionNode):
    """Represents the call operation of a method in the machine data model.

    When executed, it calls the method with the specified arguments and stores
    the return values in the context.

    Attributes:
        _args (list[Any]):
            The list of positional arguments to pass to the method.
        _kwargs (dict[str, Any]):
            The dictionary of keyword arguments to pass to the method.

    """

    _args: list[Any]
    _kwargs: dict[str, Any]
    _on_unmet: OnUnmet | None
    _timeout: float | None

    def __init__(
        self,
        method_node: str,
        args: list[Any],
        kwargs: dict[str, Any],
        successors: list["ControlFlowNode"] | None = None,
        on_unmet: OnUnmet | str | None = None,
        timeout: float | None = None,
    ):
        """Initialize a new CallMethodNode instance.

        Args:
            method_node (str):
                The identifier of the method node in the machine data model.
            args (list[Any]):
                The list of positional arguments to pass to the method.
            kwargs (dict[str, Any]):
                The dictionary of keyword arguments to pass to the method.
            successors (list["ControlFlowNode"] | None):
                A list of control flow nodes that are successors of the current
                node.
            on_unmet (OnUnmet | str | None):
                What to do when the callee has `requires` that do not hold:
                `wait` or `fail`. There is no default: a callee that has
                `requires` must be called by a node that says which.
            timeout (float | None):
                Seconds to wait for the `requires` of the callee to hold. Only
                meaningful with `on_unmet = wait`.

        Raises:
            ValueError:
                If `on_unmet` is not `wait` or `fail`, if `timeout` is not a
                positive finite number, or if `timeout` is given without
                `on_unmet = wait`.

        """
        super().__init__(node=method_node, successors=successors)
        self._args = args
        self._kwargs = kwargs
        self._on_unmet = self._validate_on_unmet(on_unmet)
        self._timeout = self._validate_timeout(timeout, self._on_unmet)

    @staticmethod
    def _validate_on_unmet(on_unmet: OnUnmet | str | None) -> OnUnmet | None:
        """Convert and check the `on_unmet` argument.

        Args:
            on_unmet (OnUnmet | str | None):
                The value given to the constructor.

        Returns:
            OnUnmet | None:
                The enum member, or None if not given.

        Raises:
            ValueError:
                If the value is not `wait` or `fail`.

        """
        if on_unmet is None or isinstance(on_unmet, OnUnmet):
            return on_unmet
        try:
            return OnUnmet(on_unmet)
        except ValueError:
            valid = ", ".join(member.value for member in OnUnmet)
            raise ValueError(
                f"Invalid on_unmet: {sanitize_detail(str(on_unmet), 32)}. "
                f"Valid values: {valid}"
            ) from None

    @staticmethod
    def _validate_timeout(
        timeout: float | None, on_unmet: OnUnmet | None
    ) -> float | None:
        """Check the `timeout` argument.

        Args:
            timeout (float | None):
                The value given to the constructor.
            on_unmet (OnUnmet | None):
                The validated `on_unmet`.

        Returns:
            float | None:
                The timeout in seconds, or None.

        Raises:
            ValueError:
                If it is not a positive finite number (a bool is not a
                number here) or `on_unmet` is not `wait`.

        """
        if timeout is None:
            return None
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, int | float)
            or not math.isfinite(timeout)
            or timeout <= 0
        ):
            raise ValueError(
                f"timeout must be a positive number of seconds, got "
                f"{sanitize_detail(repr(timeout), 32)}"
            )
        if on_unmet is not OnUnmet.WAIT:
            raise ValueError("timeout is only meaningful with on_unmet: wait")
        return timeout

    @property
    def on_unmet(self) -> OnUnmet | None:
        """Get what the node does when the callee rejects the call.

        Returns:
            OnUnmet | None:
                `wait`, `fail` or None if not specified.

        """
        return self._on_unmet

    @property
    def timeout(self) -> float | None:
        """Get the seconds to wait for the `requires` of the callee.

        Returns:
            float | None:
                The timeout in seconds, or None for no timeout.

        """
        return self._timeout

    @property
    def args(self) -> list[Any]:
        """Get the list of positional arguments to pass to the method.

        Returns:
            list[Any]:
                The list of positional arguments to pass to the method.

        """
        return self._args

    @property
    def kwargs(self) -> dict[str, Any]:
        """Get the dictionary of keyword arguments to pass to the method.

        Returns:
            dict[str, Any]:
                The dictionary of keyword arguments to pass to the method.

        """
        return self._kwargs

    def release(self, context: ExecutionContext) -> list[FrostMessage]:
        """Release what this node holds: a wait and a pending callee.

        The subscriptions of a wait on the `requires` of the callee (and its
        deadline) are removed, then the pending callee context, if any, is
        dropped and released. Safe to call more than once.

        Args:
            context (ExecutionContext):
                The context of the control flow graph.

        Returns:
            list[FrostMessage]:
                The messages produced by releasing the callee context (for
                example a remote unsubscribe).

        """
        from machine_data_model.nodes.composite_method import (
            composite_method_node,
        )

        try:
            pending_key = f"call_method_pending_{context.get_pc()}"
            if not context.has_value(pending_key):
                return []
            pending_context_id = context.get_value(pending_key)
            context.delete_value(pending_key)
            ref_method = self._get_ref_node(context)
            if isinstance(
                ref_method, composite_method_node.CompositeMethodNode
            ):
                return ref_method.abort_context(pending_context_id)
            return []
        finally:
            self._clear_wait(context)

    def _deadline_key(self, context: ExecutionContext) -> str:
        """Return the context key that holds the deadline of the wait."""
        return f"call_method_deadline_{context.get_pc()}"

    def _deadline_passed(self, context: ExecutionContext) -> bool:
        """Start the deadline at the first wait and tell whether it is over.

        The deadline is stored on the first rejection and compared on the
        following ones. It uses `time.monotonic()`, which clock changes do not
        move; contexts are not serialized, so the value never leaves the
        process. Nothing wakes the context by itself when the deadline comes:
        it is noticed when something resumes the context.

        Args:
            context (ExecutionContext):
                The context of the control flow graph.

        Returns:
            bool:
                True if the node has a timeout and its deadline is over. Always
                False on the first wait and when there is no timeout.

        """
        if self._timeout is None:
            return False
        key = self._deadline_key(context)
        if not context.has_value(key):
            context.set_value(key, time.monotonic() + self._timeout)
            return False
        return bool(time.monotonic() >= context.get_value(key))

    def _timeout_error(
        self, ref_method: MethodNode, last: ExecutionError
    ) -> ExecutionError:
        """Build the error of a wait whose deadline passed.

        Args:
            ref_method (MethodNode):
                The callee.
            last (ExecutionError):
                The rejection of the last attempt, which says what was unmet.

        Returns:
            ExecutionError:
                A `TIMEOUT` error naming the callee, the timeout and the last
                unmet conditions (bounded; the observed value is left out).

        """
        assert self._timeout is not None
        return ExecutionError(
            ExecutionErrorCode.TIMEOUT,
            sanitize_detail(
                f"call of '{ref_method.qualified_name}' timed out after "
                f"{self._timeout:g} s: {last.message}",
                _MAX_TIMEOUT_MESSAGE,
            ),
            node=ref_method.qualified_name,
            origin=last.node,
        )

    def _wait_key(self, context: ExecutionContext) -> str:
        """Return the context key that holds the variables being watched."""
        return f"call_method_wait_{context.get_pc()}"

    def _watch(
        self, context: ExecutionContext, variables: tuple[VariableNode, ...]
    ) -> bool:
        """Subscribe the context to the variables the callee reads.

        One subscription object per context is shared by all the variables, as
        `WaitConditionNode` does for its one variable, so that concurrent
        contexts never share a subscription. A variable the context is already
        subscribed to is left alone; one that is no longer needed is dropped.

        Args:
            context (ExecutionContext):
                The context of the control flow graph.
            variables (tuple[VariableNode, ...]):
                The variables the `requires` of the callee read.

        Returns:
            bool:
                True if at least one new subscription was added.

        """
        key = self._wait_key(context)
        watched: list[tuple[VariableNode, VariableSubscription]] = (
            list(context.get_value(key)) if context.has_value(key) else []
        )
        callback = context.get_subscription_callback()
        shared = (
            watched[0][1]
            if watched
            else VariableSubscription(
                subscriber_id=context.id(), subscription_callback=callback
            )
        )
        if callback is not None and shared.subscription_callback is None:
            shared.subscription_callback = callback

        wanted = {id(variable) for variable in variables}
        kept: list[tuple[VariableNode, VariableSubscription]] = []
        for variable, subscription in watched:
            if id(variable) in wanted:
                kept.append((variable, subscription))
            else:
                variable.unsubscribe(subscription)

        added = False
        known = {id(variable) for variable, _ in kept}
        for variable in variables:
            if id(variable) in known:
                continue
            existing = variable.find_subscription_by_subscriber(context.id())
            if existing is not None and existing is not shared:
                if (
                    existing.subscription_callback is None
                    and callback is not None
                ):
                    existing.subscription_callback = callback
                kept.append((variable, existing))
                continue
            if variable.subscribe(shared):
                added = True
            kept.append((variable, shared))
        context.set_value(key, kept)
        return added

    def _would_pass(
        self,
        ref_method: MethodNode,
        args: list[Any],
        kwargs: dict[str, Any],
    ) -> bool:
        """Tell whether the `requires` of the callee hold now, without calling.

        Args:
            ref_method (MethodNode):
                The callee.
            args (list[Any]):
                The resolved positional arguments of the call.
            kwargs (dict[str, Any]):
                The resolved keyword arguments of the call.

        Returns:
            bool:
                True if a call made now would pass the check.

        """
        try:
            ref_method._check_requires(
                ref_method._resolve_arguments(*args, **kwargs)
            )
        except MethodPreconditionError:
            return False
        return True

    def _unwatch(self, context: ExecutionContext) -> None:
        """Unsubscribe from the watched variables, keeping the deadline.

        Args:
            context (ExecutionContext):
                The context of the control flow graph.

        """
        key = self._wait_key(context)
        if not context.has_value(key):
            return
        watched = context.get_value(key)
        context.delete_value(key)
        for variable, subscription in watched:
            variable.unsubscribe(subscription)

    def _clear_wait(self, context: ExecutionContext) -> None:
        """Unsubscribe from the watched variables and forget the wait.

        The deadline is forgotten too.

        Args:
            context (ExecutionContext):
                The context of the control flow graph.

        """
        deadline_key = self._deadline_key(context)
        if context.has_value(deadline_key):
            context.delete_value(deadline_key)
        self._unwatch(context)

    @staticmethod
    def _wrap_error(error: ExecutionError, callee: str) -> ExecutionError:
        """Build the error of this node from the error of the callee.

        Args:
            error (ExecutionError):
                The error of the callee.
            callee (str):
                The resolved qualified name of the callee.

        Returns:
            ExecutionError:
                An error with the same code, a message prefixed with the name
                of the callee, the callee as the failing node and the origin
                of the callee error preserved (or, if it has none, the node it
                reports) and the observed value of the callee error kept.

        """
        return ExecutionError(
            code=error.code,
            message=f"{callee}: {error.message}",
            node=callee,
            origin=error.origin if error.origin is not None else error.node,
            observed=error.observed,
        )

    def execute(self, context: ExecutionContext) -> ExecutionNodeResult:
        """Execute the call operation of the method in the machine data model.

        Args:
            context (ExecutionContext):
                The context of the control flow graph.

        Returns:
            ExecutionNodeResult:
                An ExecutionNodeResult indicating success, that the callee is
                still running, or that the callee failed (the error of the
                callee is propagated).

        """
        from machine_data_model.nodes.composite_method import (
            composite_method_node,
        )

        ref_method = self._get_ref_node(context)
        assert isinstance(ref_method, MethodNode)

        data_model_id = ""
        if ref_method.data_model is not None:
            data_model_id = ref_method.data_model.name

        pending_key = f"call_method_pending_{context.get_pc()}"

        if isinstance(ref_method, composite_method_node.CompositeMethodNode):
            try:
                pending_context_id = context.get_value(pending_key)
            except KeyError:
                pending_context_id = None

            if pending_context_id is not None:
                if not ref_method.is_terminated(pending_context_id):
                    trace_control_flow_step(
                        node_id=self.node,
                        node_type=type(self).__name__,
                        execution_result=False,
                        program_counter=context.get_pc(),
                        source=context.id(),
                        data_model_id=data_model_id,
                    )
                    return execution_failure()

                if ref_method.has_failed(pending_context_id):
                    callee_error = ref_method.get_error(pending_context_id)
                    assert callee_error is not None
                    ref_method.delete_context(pending_context_id)
                    context.delete_value(pending_key)
                    trace_control_flow_step(
                        node_id=self.node,
                        node_type=type(self).__name__,
                        execution_result=False,
                        program_counter=context.get_pc(),
                        source=context.id(),
                        data_model_id=data_model_id,
                    )
                    return execution_error(
                        self._wrap_error(
                            callee_error, ref_method.qualified_name
                        )
                    )

                ret = ref_method.get_completed_return_values(pending_context_id)
                assert ret is not None
                context.set_all_values(**ret)
                ref_method.delete_context(pending_context_id)
                context.delete_value(pending_key)

                trace_control_flow_step(
                    node_id=self.node,
                    node_type=type(self).__name__,
                    execution_result=True,
                    program_counter=context.get_pc(),
                    source=context.id(),
                    data_model_id=data_model_id,
                )
                return execution_success()

        # Trace the control flow step.
        trace_control_flow_step(
            node_id=self.node,
            node_type=type(self).__name__,
            execution_result=True,
            program_counter=context.get_pc(),
            source=context.id(),
            data_model_id=data_model_id,
        )

        # resolve variables in the context
        args = [resolve_value(arg, context) for arg in self._args]
        kwargs = {k: resolve_value(v, context) for k, v in self._kwargs.items()}
        if ref_method.requires and self._on_unmet is None:
            # A callee with `requires` must be called by a node that says what
            # to do when they do not hold. Failing here, before the call and
            # whether they hold or not, keeps the result independent of the
            # data: a model that is wrong fails every time, not only when a
            # condition happens to be unmet.
            return execution_error(
                ExecutionError(
                    ExecutionErrorCode.INVALID_CONFIGURATION,
                    f"call of '{ref_method.qualified_name}': the method has "
                    "requires, so the call node must set on_unmet to 'wait' "
                    "or 'fail'",
                    node=ref_method.qualified_name,
                )
            )
        res = None
        for _ in range(_MAX_WAIT_CYCLES):
            # The wait is dropped while the callee runs: a callee that writes
            # a variable it watches would otherwise wake this very context in
            # the middle of its own call and be called again.
            self._unwatch(context)
            try:
                res = ref_method(*args, **kwargs)
                break
            except MethodPreconditionError as exp:
                # The callee's `requires` do not hold: nothing started, and
                # this is an ordinary failure of the call, not an unexpected
                # one.
                if (
                    self._on_unmet is not OnUnmet.WAIT
                    or exp.error.code
                    is ExecutionErrorCode.INVALID_CONFIGURATION
                ):
                    # `fail`, or a configuration error: never waited on.
                    self._clear_wait(context)
                    return execution_error(
                        self._wrap_error(exp.error, ref_method.qualified_name)
                    )
                if self._deadline_passed(context):
                    # This was the last attempt: the call was tried again
                    # now, after the deadline, and the requires still do not
                    # hold.
                    self._clear_wait(context)
                    return execution_error(
                        self._timeout_error(ref_method, exp.error)
                    )
                self._watch(context, exp.variables)
                if not self._would_pass(ref_method, args, kwargs):
                    return execution_failure()
                # The values changed between the check that rejected the call
                # and the subscription (no event reached us): try again, with
                # the wait dropped as for any call.
        if res is None:
            # Kept changing under us: stay subscribed, the next change wakes
            # the context.
            return execution_failure()
        self._clear_wait(context)

        if res.error is not None:
            return execution_error(
                self._wrap_error(res.error, ref_method.qualified_name),
                list(res.messages or []),
            )

        if isinstance(ref_method, composite_method_node.CompositeMethodNode):
            pending_context_id = res.return_values.get("@context_id")
            if pending_context_id is not None:
                context.set_value(pending_key, pending_context_id)

                parent_method = None
                if self.parent_cfg is not None:
                    parent_method = self.parent_cfg.composite_method_node

                if parent_method is not None:
                    child_context = ref_method._get_context(pending_context_id)
                    child_context.set_value(
                        "__nested_parent_method__",
                        parent_method,
                    )
                    child_context.set_value(
                        "__nested_parent_context_id__", context.id()
                    )

                return execution_failure(list(res.messages or []))

        context.set_all_values(**res.return_values)
        return execution_success(list(res.messages or []))

    def __eq__(self, other: object) -> bool:
        """Check equality with another object.

        Args:
            other (object):
                The object to compare with.

        Returns:
            bool:
                True if the objects are equal, False otherwise.

        """
        if self is other:
            return True

        if not isinstance(other, CallMethodNode):
            return False

        return (
            super().__eq__(other)
            and self.args == other.args
            and self.kwargs == other.kwargs
            and self.on_unmet == other.on_unmet
            and self.timeout == other.timeout
        )


class WaitConditionNode(LocalExecutionNode):
    """Represents a wait condition in the control flow graph.

    When executed, it compares the value of a variable with a constant value or
    another variable. It returns immediately if the condition is met, otherwise
    it subscribes to the variable and waits for the value to change.

    Attributes:
        _rhs (Any):
            The right-hand side of the comparison. It can be a constant value or
            reference to a variable in the context.
        _op (WaitConditionOperator):
            The comparison operator.
        _subscription (VariableSubscription | None):
            The subscription to the variable for change notifications.

    """

    _rhs: Any
    _op: WaitConditionOperator
    _subscription: VariableSubscription | None

    def __init__(
        self,
        variable_node: str,
        rhs: Any,
        op: WaitConditionOperator,
        successors: list["ControlFlowNode"] | None = None,
    ):
        """Initialize a new WaitConditionNode instance.

        Args:
            variable_node (str):
                The identifier of the variable node in the machine data model.
            rhs (Any):
                The right-hand side of the comparison. It can be a constant
                value or reference to a variable in the context.
            op (WaitConditionOperator):
                The comparison operator.
            successors (list["ControlFlowNode"] | None):
                A list of control flow nodes that are successors of the current
                node.

        """
        super().__init__(node=variable_node, successors=successors)
        self._rhs = rhs
        self._op = op

    # Per-context subscriptions are stored on the ExecutionContext to
    # avoid reusing the same subscription object across different
    # invocations of the same control flow node.

    @property
    def rhs(self) -> Any:
        """Get the right-hand side of the comparison.

        Returns:
            Any:
                The right-hand side of the comparison.

        """
        return self._rhs

    @property
    def op(self) -> WaitConditionOperator:
        """Get the comparison operator.

        Returns:
            WaitConditionOperator:
                The comparison operator.

        """
        return self._op

    def execute(self, context: ExecutionContext) -> ExecutionNodeResult:
        """Execute the wait condition in the control flow graph.

        If the condition is met, it returns immediately. Otherwise, it
        subscribes to the variable and returns failure.

        Args:
            context (ExecutionContext):
                The context of the control flow graph.

        Returns:
            ExecutionNodeResult:
                An ExecutionNodeResult indicating whether the condition was met.

        """
        ref_variable = self._get_ref_node(context)
        assert isinstance(ref_variable, VariableNode)

        # Get the data model id for tracing.
        data_model_id = ""
        if ref_variable.data_model is not None:
            data_model_id = ref_variable.data_model.name

        rhs = resolve_value(self._rhs, context)
        lhs = ref_variable.read()
        result = compare(self._op, lhs, rhs)

        # Build base keys used to store wait-related data inside the context.
        # Use a single base so derived keys are colocated and consistent.
        base_wait_key = f"wait_{self.node}_{context.id()}"

        # Create a unique wait key per context to avoid collisions.
        wait_key = f"{base_wait_key}_start"

        # Save the outcome for tracing.
        outcome = execution_success() if result else execution_failure()

        # Trace the control flow step.
        trace_control_flow_step(
            node_id=self.node,
            node_type=type(self).__name__,
            execution_result=outcome.success,
            program_counter=context.get_pc(),
            source=context.id(),
            data_model_id=data_model_id,
        )

        # Create or retrieve a subscription object specific to this context so
        # that multiple concurrent invocations of the same composite method do
        # not share the same subscription (which would bind them to the same
        # subscriber id / correlation id).
        sub_key = f"{base_wait_key}_subscription"
        subscription = None
        try:
            subscription = context.get_value(sub_key)
        except KeyError:
            subscription = None

        subscription_callback = context.get_subscription_callback()

        if subscription is None:
            # Create a new subscription for this context. Leave correlation_id
            # unspecified so the VariableSubscription constructor generates a
            # unique id for the subscription (previous behavior).
            subscription = VariableSubscription(
                subscriber_id=context.id(),
                subscription_callback=subscription_callback,
            )
            # store the subscription in the context for later retrieval
            context.set_value(sub_key, subscription)
        elif (
            subscription_callback is not None
            and subscription.subscription_callback is None
        ):
            subscription.subscription_callback = subscription_callback

        # One wait subscription per (variable, context): adopt the one that is
        # already there instead of adding a second that would wake the context
        # twice.
        existing = ref_variable.find_subscription_by_subscriber(context.id())
        if existing is not None and existing is not subscription:
            if (
                existing.subscription_callback is None
                and subscription_callback is not None
            ):
                existing.subscription_callback = subscription_callback
            subscription = existing
            context.set_value(sub_key, existing)

        # Condition not met - start waiting
        if not result:
            if subscription not in ref_variable.get_subscriptions():
                # First time waiting for this condition
                start_time = trace_wait_start(
                    variable_id=ref_variable.id,
                    condition=f"{lhs} {self._op.value} {rhs}",
                    expected_value=rhs,
                    source=f"{ref_variable.qualified_name} "
                    f"(context: {context.id()})",
                    data_model_id=data_model_id,
                )
                # Store the start time of the wait inside the context.
                context.set_value(wait_key, start_time)
                # Subscribe to the variable to be notified when its value
                # changes. We rely on the Subscription object being unique to
                # the context so that unsubscribe will remove the correct
                # subscription later.
                ref_variable.subscribe(subscription)

        # Condition met - stop waiting
        else:
            # Unsubscribe if we were subscribed.
            ref_variable.unsubscribe(subscription)
            # Remove the subscription stored in the context
            context.delete_value(sub_key)
            # If the wait key is in the context, it means we were waiting.
            if context.has_value(wait_key):
                start_time = context.get_value(wait_key)
                trace_wait_end(
                    variable_id=ref_variable.id,
                    start_time=start_time,
                    source=f"{ref_variable.qualified_name} "
                    f"(context: {context.id()})",
                    data_model_id=data_model_id,
                )
                # Remove the wait key from the context.
                context.delete_value(wait_key)

        # Return the outcome.
        return outcome

    def release(self, context: ExecutionContext) -> list[FrostMessage]:
        """Remove the wait subscription and the context keys of this node.

        Args:
            context (ExecutionContext):
                The context of the control flow graph.

        Returns:
            list[FrostMessage]:
                Always empty: the subscription is local.

        """
        base_wait_key = f"wait_{self.node}_{context.id()}"
        sub_key = f"{base_wait_key}_subscription"
        wait_key = f"{base_wait_key}_start"
        subscription = None
        if context.has_value(sub_key):
            subscription = context.get_value(sub_key)
        try:
            if subscription is not None:
                ref_variable = self._get_ref_node(context)
                assert isinstance(ref_variable, VariableNode)
                ref_variable.unsubscribe(subscription)
        finally:
            for key in (sub_key, wait_key):
                if context.has_value(key):
                    context.delete_value(key)
        return []

    def __eq__(self, other: object) -> bool:
        """Check equality with another object.

        Args:
            other (object):
                The object to compare with.

        Returns:
            bool:
                True if the objects are equal, False otherwise.

        """
        if self is other:
            return True

        if not isinstance(other, WaitConditionNode):
            return False

        if self.op != other.op or self.rhs != other.rhs:
            return False

        return super().__eq__(other)
