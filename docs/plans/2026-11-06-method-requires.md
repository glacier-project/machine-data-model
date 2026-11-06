# Plan: `requires` (preconditions) on method nodes

Status: approved decisions (D1-D5, P1-P4); implementation in progress (phases 1
and 2 done and reviewed, phase 3 implemented, its review fixes being applied by
the worker). Author: researcher. Date: 2026-11-06. Revision 3 folded in the
phase 2 review (ConditionError, `evaluate_on` split, load-time check of
`requires` paths, "has received a value" mechanism, read exceptions). Revision
4 folds in the phase 3 review (terminal states are final, limits 9.5 and 9.6,
follow-up design in section 11).
Paths are relative to the repository root. Line numbers refer to `dev` at
`d9f2c59` and may drift.

## 1. Goal and scope

Let a `MethodNode` (and `AsyncMethodNode`, `CompositeMethodNode`) declare
`requires`: a list of conditions on data model variables that must hold for the
method to be callable. A direct call (`MethodNode.__call__`, Frost `INVOKE`)
is rejected when they do not hold. Inside a control flow graph (CFG),
`CallMethodNode` chooses between waiting and failing through `on_unmet`.

In scope:

- a pure `Condition` primitive (tri-state result), shared with
  `WaitConditionNode`;
- a `FAILURE` outcome for CFG nodes and composite methods, with an error
  object;
- `requires` on methods, builder, dumper, equality, Frost mapping;
- `CallMethodNode.on_unmet` and `timeout`.

Out of scope (documented, not done here):

- `IfNode`, `Fallback`, retries, branching of any kind;
- a real timer (only a deadline checked on resume);
- `CallRemoteMethodNode` / `WaitRemoteEventNode` semantics and routing of
  remote Frost `ERROR` messages (see 9.3);
- connection-state API on connectors;
- OPC UA `Executable` attribute exposure (the `is_executable()` helper is the
  hook for it).

## 2. Decisions (approved)

| Id | Decision |
|----|----------|
| D1 | `CallMethodNode` gets `on_unmet: wait \| fail`, with **no implicit default**. Load fails if the callee has `requires` and `on_unmet` is missing. `wait` is an atomic attempt-call (no `WaitCondition` + call race). Optional `timeout`, checked on resume against a deadline stored in the context. |
| D2 | `ExecutionNodeResult.status` in `{SUCCESS, RUNNING, FAILURE}` plus optional `ExecutionError(code, message, node)`. `.success` stays (`== SUCCESS`). `execution_failure()` keeps meaning RUNNING. New `execution_error(...)`. Codes: `PRECONDITION_NOT_MET`, `NO_DATA`, `TIMEOUT`, room for remote errors. |
| D3 | `Condition` evaluates to `ok \| failed \| no_data`. `no_data` behaves like `failed` for flow but has a distinct code. Not configurable yet. |
| D4 | Field name `requires`: list of `{variable, operator, rhs}` mappings, AND semantics, no new YAML tag. Dumper emits it only when non-empty. Name `pre_call` is avoided (already an attribute). `MethodNode.__call__` never waits. Expose `evaluate_requires()` and `is_executable()`. |
| D5 | `requires` may reference method parameters. |

Decisions taken by this plan, approved by the user (see section 10):

- P1. Nodes that return `FAILURE` clean up their own subscriptions and context
  keys before returning, instead of the run loop doing it (the loop does not
  know which keys a node owns).
- P2. Callee not statically resolvable (templated path) and `on_unmet` missing:
  runtime `FAILURE` with code `INVALID_CONFIGURATION`, not a load error.
- P3. `requires` is evaluated with cached values (`force_remote_read=False`).
- P4. Remote callees (`CallRemoteMethodNode`) are untouched.

## 3. Facts the plan relies on

- `ExecutionNodeResult(success: bool, messages)` at
  `machine_data_model/behavior/control_flow_node.py:17`. `False` means "step not
  done, keep pc" (RUNNING). Only 3 call sites build it directly.
- `ControlFlow.execute` (`behavior/control_flow.py`) is linear: on `False` it
  returns with the context still active; after the last node it calls
  `context.deactivate()`.
- `ControlFlowStatus.FAILED` exists (`behavior/execution_context.py:133`) and
  `is_active()` already treats it as inactive, but nothing sets it. Four
  consumers treat "inactive" as "completed":
  `CompositeMethodNode._terminate_execution`,
  `CallMethodNode.execute` pending branch (`behavior/local_execution_node.py`
  ~454-470), `CompositeMethodNode._notify_nested_parent`,
  `FrostProtocolMng._resume_composite_method`
  (`protocols/frost_v1/frost_protocol_mng.py` ~610-650).
- `WaitConditionNode` (`behavior/local_execution_node.py:578`) has the comparison
  as an inline `if/elif` chain mixed with tracing and subscription handling. It
  calls `ref_variable.read()` (default `force_remote_read=True`).
- Per-context wait subscription lives in context keys
  `wait_<node>_<ctx>_subscription` and `_start`. Variable change ->
  `notify_subscribers` -> `FrostProtocolMng._update_variable_callback` ->
  `resume_composite_method` -> `resume_execution`. Level-triggered.
- `VariableNode.subscribe` dedups by subscription identity
  (`nodes/variable_node.py` ~218-241).
- Builder: `_build_kwargs` rejects unknown keys (`builder/data_model_builder.py`
  :53-83). Method defaults at :261-292, composite at :554-581 (its default
  dict has no `connector_name` / `remote_resource_spec`), `CallMethodNode` parse
  at :400-427.
- Dumper: common method fields `builder/data_model_dumper.py` :343-359,
  `CallMethodNode` :526-549, composite :409-440.
- `DataModel._resolve_local_cfg_nodes` (`data_model.py` ~331-352) links CFG nodes
  to data model nodes after traversal registration.
- `MethodNode.__call__` (`nodes/method_node.py:359`) calls
  `trace_method_start` (:379) before `_pre_call` and `trace_method_end` (:399)
  at the end. `CompositeMethodNode.__call__` does **not** call
  `super().__call__`; it resolves arguments, runs `_pre_call` and
  `_start_execution`.
- `FrostProtocolMng._create_error_message` (:708) always sends
  `ErrorCode.BAD_REQUEST`, whatever the `ErrorMessages` value. The `ERROR`
  branch of `handle_message` (:269) asserts the payload and returns `None`.
- Project style (`.github/copilot-instructions.md`): Google docstrings, summary
  line on the line after `"""`, lines under 79 chars, comments on their own line
  above the code.

## 4. Target design

### 4.1 New leaf modules (no imports of node classes, avoids cycles)

`machine_data_model/behavior/execution_error.py`

```python
class ExecutionErrorCode(str, Enum):
    PRECONDITION_NOT_MET = "precondition_not_met"
    NO_DATA = "no_data"
    TIMEOUT = "timeout"
    INVALID_CONFIGURATION = "invalid_configuration"
    # reserved, not produced yet
    REMOTE_ERROR = "remote_error"

@dataclass(frozen=True)
class ExecutionError:
    code: ExecutionErrorCode
    message: str
    node: str | None = None   # qualified name of the node that failed
```

`machine_data_model/behavior/condition.py`

```python
class WaitConditionOperator(str, Enum): ...   # moved from local_execution_node
def compare(op: WaitConditionOperator, lhs: Any, rhs: Any) -> bool: ...

class ConditionResult(str, Enum):
    OK = "ok"; FAILED = "failed"; NO_DATA = "no_data"

@dataclass(frozen=True)
class ConditionOutcome:
    result: ConditionResult
    message: str            # "/plant/conveyor/mode == 2 (observed 1)"
    variable: str           # resolved path

@dataclass(frozen=True)
class Condition:
    variable: str           # DM path or id; may contain ${param}
    operator: WaitConditionOperator
    rhs: Any                # literal or ${param}
    def __post_init__(self)                     # operator must be an enum member
    def resolve(self, resolve_node, scope) -> ResolvedCondition
    def evaluate(self, resolve_node, scope, force_remote_read=False)
        -> ConditionOutcome                     # resolve + evaluate_on
    def evaluate_on(self, variable, rhs, force_remote_read=False)
        -> ConditionOutcome                     # on an already resolved node
    def variables(self, resolve_node, scope) -> list[VariableNode]

class ConditionError(ValueError):
    variable: str   # resolved path, or the unresolved text
```

`ConditionResult` stays tri-state (`ok | failed | no_data`). A condition that
cannot be evaluated because it is **wrongly configured** is not "unknown data":
`resolve` / `evaluate` / `variables` raise `ConditionError` when the node is
missing, is not a `VariableNode`, when `scope` is `None` and a template is
present, or (as `KeyError`) when a template names a value missing from the
scope. Consumers map all of these to `INVALID_CONFIGURATION` (5, phases 4-5).
`ResolvedCondition` is a small frozen dataclass `(path, variable, rhs)`; the
split lets phase 5 resolve once and use the result both to subscribe
(`variables`) and to evaluate (`evaluate_on`).

- `WaitConditionOperator` stays importable from
  `behavior.local_execution_node` (re-export) because tests import it there.
- `resolve_node: Callable[[str], DataModelNode | None]`, `scope` is an
  `ExecutionContext` (or `None`). Template resolution reuses
  `resolve_string_in_context` / `resolve_value`.
- `no_data` when: the value is `None`; a remote variable has no connector; a
  remote variable has never received a value (phase 4, item 4.F); the read
  fails with a connection-type error (phase 4, item 4.G); the comparison raises
  `TypeError` (e.g. `None < 5`). A missing or non-variable node is **not**
  `no_data`: it raises `ConditionError` (configuration error). Connection state
  is not observable today (connectors only have `connect/disconnect`).
- Import cycle check: `condition.py` imports `nodes.variable_node` only under
  `TYPE_CHECKING` plus a local import inside functions if needed.
  `nodes/method_node.py` will import `behavior.condition`; acceptance for
  phase 2 includes an import test of every module in isolation.

### 4.2 Result and context

```python
class NodeStatus(Enum): SUCCESS; RUNNING; FAILURE

class ExecutionNodeResult:
    def __init__(self, success_or_status: bool | NodeStatus,
                 messages=None, error: ExecutionError | None = None)
    status: NodeStatus
    error: ExecutionError | None
    @property success -> status is SUCCESS   # read-only
    @property failed  -> status is FAILURE

def execution_success(messages=None)        # unchanged
def execution_failure(messages=None)        # unchanged meaning: RUNNING
def execution_error(error, messages=None)   # new: FAILURE
```

`bool` input keeps old call sites valid: `True` -> SUCCESS, `False` ->
RUNNING. `ExecutionContext` gets `error` (property) and `fail(error)` which sets
`status = FAILED`, stores the error, clears `active_request`.

### 4.3 Method node

```python
class MethodNode:
    def __init__(..., requires: Sequence[Condition] | None = None)
    @property requires -> list[Condition]
    def evaluate_requires(self, **kwargs) -> list[ConditionOutcome]
    def is_executable(self, **kwargs) -> bool
    def _check_requires(self, kwargs) -> None   # raises MethodPreconditionError

class MethodPreconditionError(Exception):
    error: ExecutionError
    outcomes: list[ConditionOutcome]
```

`_check_requires` is the single shared helper. It is called from
`MethodNode.__call__` and `CompositeMethodNode.__call__`, after
`_resolve_arguments` and **before** `trace_method_start` / `_pre_call` (so no
unmatched start trace, no side effects on rejection). `AsyncMethodNode`
inherits `MethodNode.__call__`.

Failure selection: any `FAILED` -> `PRECONDITION_NOT_MET`; else any `NO_DATA`
-> `NO_DATA`. Message lists every unmet condition.

Scope for evaluation: a throwaway `ExecutionContext("requires")` filled with
`set_all_values(**kwargs)` (not the constructor, so a parameter called
`context_id` does not collide). No registration anywhere.

### 4.4 CFG call node

`CallMethodNode(method_node, args, kwargs, on_unmet=None, timeout=None,
successors=None)`; `on_unmet: OnUnmet | None`, `OnUnmet(str, Enum)` =
`wait | fail`.

`execute` flow (new part only):

1. Resolve callee, args (unchanged).
2. Try the call. `MethodPreconditionError` caught:
   - `on_unmet is fail` -> `execution_error(err.error)`.
   - `on_unmet is wait` -> deadline check (timeout), subscribe to
     `Condition.variables(...)` of the callee with the per-context
     subscription (same keys pattern as `WaitConditionNode`), return RUNNING.
   - `on_unmet is None` -> `execution_error(INVALID_CONFIGURATION)`.
3. On a later resume the same node re-attempts at the same pc. On success the
   subscriptions and keys are removed (same cleanup as the wait branch).
4. Deadline: first `wait` stores `call_method_deadline_<pc>` (epoch seconds from
   `time.monotonic()` is not serialisable across processes, use
   `time.time()`); each re-execution compares and returns
   `execution_error(TIMEOUT)`. Nothing wakes the context by itself (known
   limit, 9.1).

### 4.5 YAML

```yaml
- !!AsyncMethodNode
  name: "setDestination"
  requires:
    - {variable: "/Plant/Operation/mode", operator: "==", rhs: 1}
    - {variable: "/Plant/Operation/main_motors", operator: "==", rhs: true}
  parameters:
    - !!NumericalVariableNode {name: "destination"}

- !!CompositeMethodNode
  name: "route"
  requires:
    - {variable: "/Plant/bay_${destination}/mode", operator: "==", rhs: 1}
  cfg:
    - !!CallMethodNode
      method: "/Plant/setDestination"
      kwargs: {destination: "${destination}"}
      on_unmet: wait       # required when the callee has requires
      timeout: 30          # optional, seconds
```

Parameter references use the existing `${name}` templates; `name` must be a
parameter of the method that declares the `requires` (checked at construction).
Variable paths follow what `WaitConditionNode.variable` accepts today.

## 5. Phases

Each phase is shippable alone and leaves `dev` green (`pytest`, `mypy`, ruff).

### Phase 1 - Characterization tests (worker, done)

Goal: pin current behavior before refactoring.

The worker's `WaitConditionNode` characterization lives in
`tests/behavior/test_wait_condition_characterization.py`.

Files: `tests/behavior/test_local_execution_node.py`,
`tests/behavior/test_wait_subscription_bug.py`,
`tests/nodes/composite_method/test_composite_method.py`,
`tests/protocols/frost_v1/test_frost_protocol_mng.py`.

Tests to have (known gaps first):

1. `WaitConditionNode`: each of the 6 operators true/false; rhs from context
   (`${x}`); `None` on the left; resume after variable change re-evaluates;
   subscription and context keys removed on success.
2. `CallMethodNode` + nested composite: pending branch (child waits, parent
   returns RUNNING, child completes, parent completes), return values copied,
   `delete_context` called, via both direct `resume_execution` and Frost.
3. Error paths as they are today (documented as current behavior, expected to
   change later): exception from a callback propagates out of
   `MethodNode.__call__`; remote `ERROR` message is dropped
   (`handle_message` returns `None`) and the context stays waiting.
4. Builder/dumper round trip of an existing composite with wait + call
   (byte-identical re-dump).

Acceptance: all pass on unchanged production code. No production file touched.
Risk: tests that encode accidental behavior (item 3) must be marked clearly so
phase 3 can update them deliberately.

### Phase 2 - Extract `Condition`

Goal: pure predicate, no behavior change.

Files:

- new `machine_data_model/behavior/condition.py`,
  `machine_data_model/behavior/execution_error.py` (only the enums/dataclasses
  needed here);
- `machine_data_model/behavior/local_execution_node.py`: `WaitConditionNode`
  uses `compare()` and `Condition.evaluate` for the comparison; keeps its
  subscription/tracing code; keeps `force_remote_read=True` (current behavior);
  re-exports `WaitConditionOperator`, `get_condition_operator`.

Tests (new `tests/behavior/test_condition.py`):

1. `compare` for 6 operators, int/float/str/bool, mixed types.
2. `Condition.evaluate`: ok, failed, `no_data` for `None` value, for remote
   variable without connector, for `TypeError`, for missing variable path.
3. `${param}` in `variable` and in `rhs`; missing template key.
4. `Condition.variables` returns the variables that would be read.
5. Import test: each of `behavior.condition`, `nodes.method_node`,
   `behavior.local_execution_node` imports first in a fresh interpreter.

Acceptance: all phase 1 tests unchanged and green; `WaitConditionNode` has no
`if/elif` operator chain; no new import cycles.
Risks: `WaitConditionNode` today raises on a `None` lhs (`TypeError`) while
`Condition` returns `no_data`; the node must keep its old outward behavior
(treat `no_data` as "not met, keep waiting"), pinned by phase 1 item 1.

### Phase 3 - `FAILURE` outcome and the four consumers

Goal: a composite can end in error, and every consumer tells it apart from
completion.

Files / changes:

1. `behavior/control_flow_node.py`: `NodeStatus`, new `ExecutionNodeResult`
   (4.2), `execution_error`. `ExecutionNodeResult(False, [msg])` in
   `remote_execution_node.py` stays RUNNING.
2. `behavior/execution_context.py`: `error`, `fail(error)`.
3. `behavior/control_flow.py` `ControlFlow.execute`: on `result.failed` call
   `context.fail(result.error)`, trace end with `success=False`, return the
   messages, do not advance pc. (Per P1, nodes clean up before returning.)
4. `nodes/method_node.py`: `MethodExecutionResult.error: ExecutionError | None
   = None` (dataclass default, old constructors unaffected).
5. `nodes/composite_method/composite_method_node.py`:
   - `_terminate_execution`: if status is `FAILED`, return `{}`; do not build
     returns, do not fill `_completed_results`, do not call `_post_call`.
   - `_start_execution` / `resume_execution`: copy `context.error` into
     `MethodExecutionResult.error`.
   - new `has_failed(context_id)`, `get_error(context_id)`; `is_terminated`
     keeps meaning completed-or-failed (document it).
   - **Fix an existing leak (found by the worker in phase 1).** A composite
     that completes synchronously is never removed from
     `CompositeMethodNode._contexts` and `_completed_results`: only the nested
     pending path (`CallMethodNode` -> `delete_context`) and the Frost
     `_resume_composite_method` path delete contexts. Same for a composite that
     now fails synchronously. Fix: when `_start_execution` /
     `resume_execution` ends in a terminal state (completed or failed) and
     nobody will collect it later, the context is released. The contract has to
     be explicit: a context that a caller still needs (the nested parent reads
     `get_completed_return_values` / `get_error` after `is_terminated`; Frost
     reads them after resume) stays until that consumer calls `delete_context`;
     a context that is already terminal when `_start_execution` returns (so
     the caller receives the result directly in `MethodExecutionResult`) is
     deleted before returning. The characterization test in
     `tests/behavior/test_wait_condition_characterization.py` that pins the
     current leak is updated in the same PR to assert the new behavior.
   - `_notify_nested_parent`: unchanged trigger (it already fires for inactive
     contexts); the parent's resume now sees the failure through item 6.
6. `behavior/local_execution_node.py` `CallMethodNode.execute`:
   - pending branch: child terminated and `has_failed` -> delete child context
     and pending key, return `execution_error(child error, node=self.node)`
     (same code, message prefixed with the callee name);
   - first-call branch: `res.error` set -> `execution_error(...)`.
7. `protocols/frost_v1/frost_protocol_mng.py`:
   - `_resume_composite_method`: if failed, delete context, remove from
     `_running_methods`, return an error response; success path unchanged.
   - `_invoke_method`: if `ret.error`, return an error response instead of
     `method_completed`.
   - `_create_error_message(msg, error_message, error_code=ErrorCode.BAD_REQUEST)`:
     new optional parameter (default keeps all current callers byte-identical).
   - `ErrorMessages` new members `PRECONDITION_NOT_MET`, `NO_DATA`, `TIMEOUT`
     (distinct texts); mapping `ExecutionErrorCode -> (ErrorCode, ErrorMessages)`:
     `PRECONDITION_NOT_MET`, `NO_DATA` -> `NOT_ALLOWED`; `TIMEOUT` ->
     the generic `UNKNOWN` code with its own `ErrorMessages.TIMEOUT` text (no
     Frost protocol change now, decided, see 10); `INVALID_CONFIGURATION` ->
     `BAD_REQUEST`.

Tests:

1. `ExecutionNodeResult` compat: `True/False` positional, `.success`, `.failed`,
   `.status`, `execution_failure()` is RUNNING, `execution_error` carries error.
2. Run loop with a stub node returning FAILURE: context `FAILED`, pc not
   advanced, error stored, later nodes not run, `is_active()` false.
3. Composite that fails: `_terminate_execution` returns `{}`, nothing cached,
   `_post_call` not called, `MethodExecutionResult.error` set.
4. Nested: child fails on first call, child fails after a wait; parent ends
   `FAILED` with the child's code; both contexts deletable; no leaked keys.
5. Frost: failed top-level composite -> error response with `NOT_ALLOWED`;
   `_running_methods` empty afterwards; completed path unchanged.
5b. Leak: after a synchronous completion and after a synchronous failure,
   `_contexts` and `_completed_results` are empty; after a nested child
   completes and the parent collects it, both are empty; a composite that stays
   pending keeps exactly one context until completion or failure.
6. Phase 1 item 3 tests updated deliberately where behavior changes.

Acceptance: phases 1-2 tests green; a stub failing node proves each of the four
consumers; no consumer reads `is_terminated` as "completed" without checking
`has_failed`.

Terminal states are final (rule added by the phase 3 review):

- `ControlFlow.execute` returns immediately, with no messages, no trace and no
  node execution, when `not context.is_active()`.
- `ExecutionContext.deactivate()` never overwrites `FAILED` (it only acts on an
  active context).
- `resume_execution` on a terminal context returns the stored outcome
  idempotently (`error` plus `{}` for `FAILED`, the cached return values for
  `COMPLETED`) and never calls `_post_call` a second time.
- Test: a context that failed on resume, resumed a second time, stays
  `FAILED`, `has_failed()` is still true, `error` is unchanged, the node at the
  failing pc is not executed again (`StubNode.runs`), `_completed_results` is
  empty. Failure scenario that motivated it: a stub returning RUNNING, then
  FAILURE, then SUCCESS ended `COMPLETED` with `error` still set after a second
  resume.

Other fixes applied after the phase 3 review (all with tests): the detail of
`ExecutionError.message` is appended to the Frost error text (the payload field
is already a free `str`, `build_error_message` accepts `ErrorMessages | str`);
`ExecutionError` keeps the root-cause node and `CallMethodNode` uses the
resolved callee path; `ExecutionNodeResult.status` / `error` are read-only;
`REMOTE_ERROR` has its own message and a test checks that every
`ExecutionErrorCode` has a Frost mapping; `_notify_nested_parent` catches
`KeyError` as well as `ValueError` and releases in `try/finally`; nested wait
under Frost is pinned by a strict `xfail` test (see 9.5 and section 11).
Risks: nested resume path (child resumes parent from inside
`_notify_nested_parent`) is the least tested part of the code; phase 1 item 2
must exist first. `ExecutionNodeResult.success` becoming read-only breaks any
code assigning it (grep found none in `machine_data_model/` or `tests/`).
Tracing events have no error field; reuse `success=False` and put the message
in `source`/log, a new trace field is a separate change.

### Phase 4 - `MethodNode.requires` and direct-call rejection

Goal: declarative `requires`, enforced on direct calls and Frost invoke.

Files / changes:

1. `nodes/method_node.py`: `requires` constructor argument on `MethodNode` and
   `AsyncMethodNode`; `MethodPreconditionError`; `_check_requires`,
   `evaluate_requires`, `is_executable`; call `_check_requires` in `__call__`
   after `_resolve_arguments`, before `trace_method_start`.
   Construction check: every `${name}` in `variable`/`rhs` is a parameter name,
   else `ValueError`.
2. `nodes/composite_method/composite_method_node.py`: `requires` argument;
   `__call__` calls the same `_check_requires` (it does not call `super()`).
3. `builder/data_model_builder.py`: add `"requires": []` to the defaults of
   `_get_method_node` (:261-292) and `_get_composite_method_node` (:554-581);
   convert each mapping to `Condition` (keys exactly `variable`, `operator`,
   `rhs`; unknown or missing keys raise `ValueError` with the same wording as
   `_build_kwargs`; operator via `get_condition_operator`).
4. `builder/data_model_dumper.py`: `_get_method_node_common_fields` (:343-359)
   adds `"requires"` **only when non-empty**, as plain mappings; composite path
   inherits it.
5. `__eq__` of `MethodNode` / `CompositeMethodNode` compares `requires`.
6. `protocols/frost_v1/frost_protocol_mng.py` `_invoke_method`: catch
   `MethodPreconditionError`, answer with the mapping of phase 3. Any other
   exception stays unhandled (unchanged).
7. `README.md`: new "Requires" subsection under Method Nodes.

Tests:

1. Direct call rejected when a condition fails; passes when all hold; AND
   semantics; no `trace_method_start` emitted on rejection; callback and
   `_pre_call` not called; variable values untouched.
2. `no_data`: variable `None`, remote variable without connector ->
   `NO_DATA` code, distinct from `PRECONDITION_NOT_MET`.
3. `evaluate_requires` / `is_executable` do not call the callback.
4. `${param}` in `variable` and `rhs`; unknown parameter reference raises at
   construction; value comes from the call arguments (positional and keyword).
5. `CompositeMethodNode` with `requires`: rejected before a context is created
   (`_contexts` empty), covers the "does not call super" case.
6. Builder: parse sync, async, composite; unknown key; missing `variable`; bad
   operator; YAML without `requires` unchanged.
7. Dumper: old fixtures re-dump byte-identical; model with `requires` round
   trips (build -> dump -> build -> `==`).
8. Frost: `INVOKE` of a method whose requires fail -> error response
   (`NOT_ALLOWED`, distinct message), method not invoked; success unchanged.
9. `__eq__` differs when `requires` differs.

#### Phase 4 additions (from the phase 2 review)

4.A **`evaluate_on` split** (step 0 of the phase, a refactor covered by the
phase 2 tests): `Condition.resolve()` returns `ResolvedCondition`;
`evaluate()` = `resolve()` + `evaluate_on()`. Phase 5 consumes it. Optional,
later and separate PR: `WaitConditionNode` evaluates through `evaluate_on` and
holds a `Condition` (for `__eq__`/dumper). That is a deliberate behavior change
(`None`/uncomparable lhs becomes `no_data` = keep waiting instead of raising
`TypeError`), so it ships with its own tests and is not part of phases 4-5.

4.B **`ConditionError` and `KeyError` never escape.** `_check_requires` wraps
every `Condition.evaluate` call: `ConditionError` and `KeyError` become
`ExecutionError(INVALID_CONFIGURATION, message naming the method, the
condition and the variable path or template name, node=qualified name)`
and are raised as `MethodPreconditionError`. Contract: `MethodNode.__call__`
and `CompositeMethodNode.__call__` raise **only** `MethodPreconditionError` for
requires problems; `FrostProtocolMng._invoke_method` catches exactly that and
maps `INVALID_CONFIGURATION` to `BAD_REQUEST`, `PRECONDITION_NOT_MET` and
`NO_DATA` to `NOT_ALLOWED`. Selection order when several conditions fail:
`INVALID_CONFIGURATION` first (stop at the first one), then
`PRECONDITION_NOT_MET`, then `NO_DATA`. `evaluate_requires()` lets
`ConditionError` propagate (it is a diagnostic helper);
`is_executable()` catches it and returns `False`.
`CallMethodNode` (phase 5) treats a callee error with code
`INVALID_CONFIGURATION` as `FAILURE` whatever `on_unmet` says: a configuration
error never waits (waiting on it would hang).

4.C **Load-time check of static `requires` paths.** Introduced in this phase,
extended in phase 5 (a small deviation: the pass starts here so that phase 4
does not ship `requires` with no load check). In `DataModel.__init__`, after
all nodes are registered, inside the existing `try`: for every method with
`requires`, every condition whose `variable` has no `${...}` must resolve to a
`VariableNode`; otherwise `ValueError` naming the method and the path.
Templated paths are checked at run time (4.B). This covers every method, not
only those called from a composite.

4.D **`scope=None` rule.** A `Condition` containing a template is never
evaluated with `scope=None` (it raises `ConditionError`). `MethodNode` always
passes the throwaway scope of 4.3, so this only matters for other callers.

4.E **Tests for 4.A-4.D:** missing path -> `INVALID_CONFIGURATION` from direct
call, from Frost `INVOKE` (`BAD_REQUEST`), from `is_executable()` (`False`);
non-variable node (folder) same; template naming a value that is not in the
call arguments same; no raw `KeyError`/`ConditionError` escapes
`__call__`/`_invoke_method`; load fails for a static bad path and does not fail
for a templated one; `Condition(op="==")` with a raw string is rejected at
construction.

4.F **"Has received a value" mechanism (DECIDED by the user: option B, the
timestamp; safety relevant).**
Problem: a remote variable that never received data reads its initial default
value, not `None` (`NumericalVariableNode._read_remote_value` returns
`_read_internal_value()` when the connector gives `None`, and the same pattern
exists in the string, boolean and object nodes; the cached read path
(`force_remote_read=False`) always returns the cache, which starts as the
constructor default). So a guard such as `mode == 0` can **pass on the default
value** before the first real update. Facts that constrain the design:
`VariableNode.read()` itself calls `_update_internal_value(value)` after every
remote read, so a flag set inside `_update_internal_value` would be set by the
first cached read of the default: the flag must be set only where a value
really originates from the remote side:

- `_remote_subscription_callback` (remote change);
- `subscribe_to_remote_changes`, the initial `connector.read_node_value` when
  its result is not `None`;
- the `force_remote_read=True` branch of `VariableNode._read_remote_value`
  (base class, which the subclasses call through `super()`) when the connector
  result is not `None`;
- a successful remote write (`_update_remote_value` returned the new value): we
  then know the value.

Options:

- **A. Boolean flag** `_remote_value_received` set at those four places;
  `has_received_value()` is `True` for local variables, the flag for remote
  ones. Smallest change. Cannot express staleness; never resets when the
  connection drops.
- **B. Timestamp** `_last_remote_update: float | None` (epoch seconds) set at
  the same four places; `has_received_value()` = local or timestamp is not
  `None`; also exposes `last_update` (age, "since"). Same change size as A plus
  one float, and it is the base for a later `max_age` / staleness guard
  (OPC UA `SourceTimestamp` analogue, the `since` of the tree-thinking checks).
- **C. Make unreceived reads return `None`** (change `_read_remote_value`).
  Rejected: changes the public `read()` contract and the declared return types
  (`float`, `str`, `bool`) of every node, large blast radius.
- **D. Quality object** (`Good/Uncertain/Bad` + timestamp, OPC UA StatusCode
  style) carried by connectors' callbacks. Most future-proof, largest change
  (connector API and `SubscriptionArguments`); a later step on top of B.

Recommendation: **B**, implemented in the base class
(`machine_data_model/nodes/variable_node.py`), with `Condition.evaluate_on`
returning `NO_DATA` ("(no value received yet)") for a remote variable whose
`has_received_value()` is `False`. `ObjectVariableNode`: received when every
property is received (empty object: `True`). Not in this phase: reset on
disconnect (needs a connector hook such as `mark_stale()`, follow-up) and
`max_age`. Tests: fake connector whose initial read is `None` -> `NO_DATA`;
after a subscription callback -> `OK`/`FAILED`; after a forced read returning a
value -> `OK`/`FAILED`; after a successful remote write; local variable always
has a value; a cached read of the default does not set the flag (regression
for the `read()` write-back); the same through `requires` on a method (call
rejected with `NO_DATA`) and `CallMethodNode` wait mode (stays RUNNING).
The phase 2 test that pins today's weakness (guard passes on the default) is
flipped by this change.

4.G **Exceptions raised by `variable.read()` (DECIDED by the user: `OSError` ->
`NO_DATA`, every other exception propagates, connector exception audit
included).** `Condition.evaluate`
catches `OSError` (covers `ConnectionError` and `TimeoutError`) around the read
and returns `NO_DATA` with message "(read failed: <type>)". Everything else
(`RuntimeError`, `AssertionError`, programming errors) propagates. With the
cached reads of P3 this is rare; it matters for `force_remote_read=True`
(phase 5, `WaitConditionNode`). Open sub-task: connector libraries raise their
own types (asyncua, aiomqtt); I did not audit them. Audit
`AbstractConnector.read_node_value` implementations and wrap connection/timeout
failures into `ConnectionError`/`TimeoutError` at the connector boundary, so
the `OSError` catch is sufficient. Tests: stub variable whose read raises
`ConnectionError`/`TimeoutError`/`RuntimeError` -> `NO_DATA`/`NO_DATA`/raises.

4.H **Frost boundary: size of the detail and disclosure of observed values
(user decision needed).** Since phase 3 the Frost error text is
`"<enum text>: <error.message>"`. From phase 4 on, `error.message` is built from
`ConditionOutcome.message`, which contains `(observed <value>)`: the current
value of a data model variable, of any type and size (a text variable can hold
megabytes or newlines), sent to the remote caller of the method, who may not be
allowed to read that variable. Nothing in the data model has an authorization
model, so "send it only if the caller may read it" is not available.
Facts: the Frost `error_message` field is a free `str`; messages also flow
through traces and logs, where the observed value is wanted for diagnosis.

Options:

- **A. Send the full message, truncated.** Simplest; discloses the observed
  value. Not recommended.
- **B. Two texts (recommended).** `ExecutionError.message` stays the internal,
  full text (traces, logs, direct-API callers). Add
  `ExecutionError.public_message: str | None = None`, the text that may leave
  the process: the failing condition without the observed value (for example
  `"/plant/conveyor/mode == 2"`, so the caller learns what must hold, not what
  the state is). `ConditionOutcome` gets a matching `detail` field and
  `MethodPreconditionError` / `_wrap_error` carry and prefix `public_message`
  the same way as `message`. Frost sends only `public_message`; when it is
  `None` it sends only the generic enum text (safe default: a new error source
  discloses nothing until it opts in).
- **C. Code only.** Safest, least useful: the client cannot tell which
  condition failed.
- **D. Configurable per data model** (`expose_error_details: true|false`).
  More flexible, one more switch to get wrong; can be added on top of B later.

Truncation (needed with any option, ships now because the Frost detail path
already exists since phase 3): one helper at the Frost boundary
(`FrostProtocolMng`, used by `_create_execution_error_message`) that collapses
whitespace and control characters to single spaces, cuts the detail to 256
characters and appends an ellipsis (`...`). Keep the limit a module constant.
The enum text is never truncated.

Tests: a 10 000-character detail is cut to the limit; newlines/tabs/control
characters never appear in the sent text; with B the observed value is absent
from the Frost message but present in `error.message`; `public_message=None`
gives the generic text only; a nested failure (`_wrap_error`) prefixes callee
paths in `public_message` and never copies the observed value; non-ASCII text
survives and the cut never splits a surrogate pair/multi-byte sequence (cut on
`str`, not `bytes`).

Recommendation: truncation now (with the phase 3 fixes), option B in phase 4.

Acceptance: all earlier tests green with no edits; new tests green; `mypy`
clean; dumper output for every existing example under `examples/` and
`resource/` is byte-identical; no `KeyError`/`ConditionError` reaches a caller
of `__call__` or Frost `_invoke_method`.
Risks: name clash with `_pre_call`/`pre_callback` (we use `requires`
everywhere, including attribute and kwarg); `requires` on a remote method
(`is_remote()`) is evaluated locally against local variables, this is intended
and must be documented; the composite builder defaults do not accept
`connector_name`, so `requires` must not assume it does.

### Phase 5 - `CallMethodNode.on_unmet` and `timeout`

Goal: CFG chooses wait or fail; atomic attempt-call; optional timeout.

Files / changes:

1. `behavior/local_execution_node.py`: `OnUnmet` enum; `CallMethodNode` new
   arguments `on_unmet`, `timeout`; `execute` per 4.4; cleanup helper shared
   with `WaitConditionNode` for the per-context subscription (key pattern
   unchanged so `test_wait_subscription_bug` keeps its meaning); `__eq__` and
   properties updated.
2. `data_model.py`: after `_register_nodes` and `_setup_inheritable_specs`
   (all nodes registered), a validation pass over every `CompositeMethodNode`
   CFG: for each `CallMethodNode` whose callee resolves statically to a
   `MethodNode` with non-empty `requires` and `on_unmet is None`, raise
   `ValueError` naming composite, call index and callee. Run it inside the
   existing `try` so connectors are cleaned up on failure. Not applied to
   `CallRemoteMethodNode` (P4). The pass already exists from phase 4 (static
   `requires` paths, 4.C); this phase adds the `on_unmet` rule to it. In wait
   mode `Condition.resolve` is called once per attempt and its result feeds both
   the subscription (`variables`) and the evaluation (`evaluate_on`); a
   `ConditionError` from it fails the node with `INVALID_CONFIGURATION` instead
   of subscribing to nothing.
3. `builder/data_model_builder.py` :400-427: add `"on_unmet": None`,
   `"timeout": None`; validate `on_unmet in {wait, fail}` and `timeout > 0`.
4. `builder/data_model_dumper.py` :526-549: emit `on_unmet` / `timeout` only
   when set.
5. `README.md` and examples: one example per mode.

Tests:

1. `fail`: requires unmet -> composite `FAILED`, code `PRECONDITION_NOT_MET`;
   `no_data` -> code `NO_DATA`; nothing called, no subscription left.
2. `wait`: RUNNING, subscribed to every variable the callee reads, resumes when
   one changes, calls exactly once; stays RUNNING if still unmet; condition
   becoming false between a variable event and the retry does not call
   (atomicity); two concurrent contexts do not share a subscription (extends
   `test_wait_subscription_bug`).
3. `timeout`: deadline set on first wait; a resume after the deadline gives
   `TIMEOUT` and removes subscriptions; no timeout means no deadline key.
4. Load-time: callee with `requires` and no `on_unmet` raises at
   `DataModelBuilder` load with the composite and callee names; callee without
   `requires` and no `on_unmet` loads; callee added later in YAML order still
   detected (validation runs after full registration); templated callee path
   skipped at load and gives `INVALID_CONFIGURATION` at run time (P2).
5. Nested composite callee with `requires` (check happens at the callee's
   `__call__`, pending-branch behavior unchanged).
6. Builder/dumper round trip with and without the new fields.

Acceptance: every earlier test green; the TOCTOU test proves there is no
separate wait-then-call sequence; no composite in `examples/` or `resource/`
changes behavior (none has `requires`).
Risks: `timeout` only fires when something resumes the context (9.1);
`time.time()` jumps can shorten/extend a timeout; subscribing to variables
read by a callee uses `VariableNode.subscribe` identity dedup, so the
subscription object must be stored in the context exactly like
`WaitConditionNode` does.

## 6. Cross-cutting items

- Every new public function/class gets a Google-style docstring; no trailing
  comments; lines under 79 characters.
- `mypy` strictness: `ExecutionNodeResult.__init__` overload for `bool` and
  `NodeStatus` so existing call sites type-check without edits.
- Tracing: no new event types. Rejected direct calls emit neither
  `trace_method_start` nor `trace_method_end`.
- Docs: README section (phase 4) and `docs/source` autoapi needs no change.
- Running tests: use `.venv/bin/python -m pytest` (the project virtualenv; the
  `aiomqtt` dependency was missing and is now installed there). Run the full
  suite, `mypy` and ruff before every phase PR.

## 7. Suggested commit/PR split

One PR per phase, in order. Phases 1-2 are pure refactor/tests (no behavior
change) and can merge without product review. Phase 3 is invisible to YAML
users. Phases 4 and 5 add the feature.

## 8. Rollback

Each phase is revertible alone: 5 -> 4 -> 3 -> 2 are strictly layered. Old YAML
files never contain the new keys, so reverting does not strand data; new YAML
with `requires` fails at load on an old build with "Unexpected keys", which is
the existing, clear failure mode.

## 9. Known limits (accepted, document in README)

1. No timer: `timeout` and `wait` need a wakeup (variable change or response). A
   composite waiting on a variable that never changes never times out until
   something calls `resume_execution`.
2. Connection state is unknown, and a remote variable that was never written
   reads its **default value, not `None`**: until phase 4 item 4.F lands, a
   guard can pass (or fail) on a stale default instead of reporting `no_data`.
   After 4.F, `no_data` means: `None`, no connector, never received a value,
   read failed with a connection error, or an uncomparable value. A value that
   was received and then went stale (connection lost later) is still treated
   as valid until a disconnect hook or `max_age` exists (follow-up).
3. Remote Frost `ERROR` messages are still dropped by
   `FrostProtocolMng.handle_message` and a `CallRemoteMethodNode` still waits
   forever on them. `ExecutionErrorCode.REMOTE_ERROR` is reserved; routing the
   error to the waiting context is a follow-up.
4. `requires` are a permissive (checked when the call starts). Conditions that
   must keep holding while a composite runs (interlocks) are not modeled.
5. **Nested composites that wait are never resumed under Frost (pre-existing,
   found in the phase 3 review).** A composite called from another composite
   (`CallMethodNode`) that blocks on a `WaitConditionNode` or on a remote
   response is not in `FrostProtocolMng._running_methods` (only top-level
   contexts are). The wait subscription's `subscriber_id` is the child context
   id, so `_update_variable_callback` does not match it and emits a spurious
   variable-update message instead of resuming; `handle_response` has the same
   gap for a remote call inside a nested composite (the correlation id is the
   child context id). Result: the parent request is never answered, contexts
   and subscriptions stay. Failure and completion propagation between nested
   composites works with direct `resume_execution` calls, not end-to-end over
   Frost. Pinned by a strict `xfail` test. Phase 5 `on_unmet: wait` and
   `timeout` inside a nested composite depend on it. Fix design: section 11.
6. **`resume_execution` does not release a terminal context** (only
   `_start_execution` does, for contexts that are already terminal when it
   returns). The consumer that resumed a context must call `delete_context`:
   the nested parent does it when it collects the child, the Frost manager does
   it for top-level contexts. A top-level context that terminates through a
   nested-notify chain (the cascade started by a child's resume) is released by
   nobody and, under Frost, its request is never answered; this is the same
   root cause as limit 5 and is fixed by section 11.
7. **An unexpected exception in a node leaves the context active at the same
   pc** (pre-existing; found by the phase 3 re-review, probe G). The exception
   propagates to whoever called `execute`/`resume_execution`; if that was a
   nested-parent notification the parent stays stuck (status `READY`, pc
   unchanged) and its subscriptions and context keys stay. Hardening design:
   section 12.
8. **Composite contexts are not thread-safe** (pre-existing, noted in the phase 3
   recheck). Variable-change callbacks run on connector threads
   (`abstract_async_connector.py` runs an asyncio loop thread; OPC UA and MQTT
   callbacks call `notify_subscribers` there), while method invocations and
   Frost requests run on other threads. `CompositeMethodNode._contexts`,
   `_completed_results`, `_notified_parent_contexts` and
   `FrostProtocolMng._running_methods` are plain dicts with no lock, and
   `delete_context` is check-then-`del`. Two concurrent resumes of the same
   context can execute a node twice; a context deleted between a pre-check and
   a resume raises from the second step. Cheap hardening: one `RLock` in
   `FrostProtocolMng` around request handling and every resume callback (single
   choke point), `delete_context` via `dict.pop` with a sentinel (atomic), and
   `_notify_nested_parent` tolerating a `ContextNotFoundError` whose id is the
   parent's. Not scheduled; the contract until then: callers serialize resumes
   of the same composite.

## 10. Decisions on the open questions, and what is still open

Decided (user approved, 2026-11-06):

1. P1 - **decided**: a node that returns `FAILURE` cleans up its own
   subscriptions and context keys before returning; the run loop does not.
2. P2 - **decided**: templated callee with missing `on_unmet` fails at run time
   (`INVALID_CONFIGURATION`), not at load.
3. P3 - **decided**: `requires` is evaluated with cached values
   (`force_remote_read=False`); `WaitConditionNode` keeps its forced remote
   read.
4. P4 - **decided**: `CallRemoteMethodNode` is untouched; remote `ERROR`
   messages stay dropped (limit 9.3, `REMOTE_ERROR` code reserved).
5. `TIMEOUT` over Frost - **decided**: no protocol change now. It is sent with
   the generic `ErrorCode.UNKNOWN` and a dedicated `ErrorMessages.TIMEOUT`
   text. A dedicated Frost `ErrorCode` can be added later without changing the
   `ExecutionErrorCode` values.
6. Operators beyond the six (`in`, `between`) - **deferred**. Adding them later
   is source-compatible because `Condition` owns the operator set.

Decided by the phase 2 review (manager, applied by the worker):

7. Missing / non-variable node, `scope=None` with a template: `ConditionError`
   (configuration error) instead of `NO_DATA`; `ConditionResult` stays
   tri-state; mapped to `INVALID_CONFIGURATION` (4.B).

Decided by the user for phase 4:

8. "Has received a value": option B, `_last_remote_update` timestamp in the
   `VariableNode` base class (4.F).
9. `read()` exceptions: `OSError` (so `ConnectionError`, `TimeoutError`) ->
   `NO_DATA`; all other exceptions propagate; audit of connector exceptions is
   part of phase 4 (4.G).
10. The `DataModel` validation pass of static `requires` paths starts in phase 4
    (4.C), phase 5 extends it.

Still open:

11. Should `on_unmet`/`timeout` also be accepted on `CallRemoteMethodNode`
    later, once remote `requires` can be discovered?
12. Follow-up (not scheduled): `WaitConditionNode` through `evaluate_on` (4.A),
    disconnect hook / `max_age`, quality object (option D of 4.F).
13. **User decision needed:** pull the nested-context routing fix (section 11)
    in before phase 5, or ship phase 5 with the limit documented. Recommended:
    before phase 5.
14. **User decision needed (phase 4):** disclosure of observed values in remote
    error text, option B of 4.H (separate `public_message`, observed value never
    sent) recommended; truncation of the detail (256 characters, one line) is
    not in question.
15. Follow-up, not scheduled: unexpected exceptions become `FAILURE`
    (section 12), priority medium.

## 11. Follow-up design: nested composite contexts under Frost

Problem (limit 9.5): only top-level composite contexts are registered in
`FrostProtocolMng._running_methods`; resumption triggers (variable change of a
wait subscription, remote response) carry the id of the context that is
actually waiting, which for a nested child is not registered. Facts:

- Wait subscription: `WaitConditionNode` creates
  `VariableSubscription(subscriber_id=context.id(), subscription_callback=
  context.get_subscription_callback())`; the callback is set only on top-level
  contexts (`set_context_subscription_callback` in `_invoke_method`), so a
  nested child gets `None` and the node-level callback installed by
  `ProtocolMng` runs: `_update_variable_callback` -> no match -> update message.
- Remote call: `CallRemoteMethodNode._create_request` uses
  `correlation_id=context.id()`; `handle_response` looks the id up in
  `_running_methods`.
- Resuming the parent does not drive the child: the pending branch of
  `CallMethodNode` only checks `is_terminated`. The existing up-cascade is
  child -> `_notify_nested_parent` -> parent `resume_execution`, so the **child
  must be resumed itself** and the cascade does the rest.
- After the cascade the top-level context may be terminal without Frost
  having been involved (limit 9.6): someone must answer the original request
  and release the context.

Needed pieces, in any option: (P1) the child context gets its parent's
subscription callback; (P2) a way to find "the composite and context for an
arbitrary context id"; (P3) after resuming a (nested) context, finish the
top-level request if it became terminal.

### Options

- **O1 - Frost-side routing (recommended).**
  P1: in `CallMethodNode`, where the pending child is registered
  (`__nested_parent_*` keys), also call
  `child_context.set_subscription_callback(context.get_subscription_callback())`
  (one line, no-op when the parent has none).
  P2: a context index. `CompositeMethodNode` registers/unregisters context ids
  in `DataModel` (`_create_context` and `delete_context` are the only two
  sites): `DataModel.find_context(ctx_id) -> tuple[CompositeMethodNode,
  ExecutionContext] | None`, O(1); composites with no data model skip it.
  Frost uses it in both `_update_variable_callback` (match on
  `subscriber_id` / `correlation_id`) and `handle_response`
  (`cm.handle_message(ctx_id, msg)` on the owning composite).
  P3: `_resume_composite_method` is split: `_resume_context(ctx_id)` resumes
  the owning composite's context (collecting `ret.messages`, which already
  include the messages produced by the parent cascade), then walks up
  `__nested_parent_context_id__` to the root id and calls an idempotent
  `_finish_if_terminated(root_id)` (the current tail of
  `_resume_composite_method`: error/completed response, `delete_context`,
  `del _running_methods[...]`; keyed on presence in `_running_methods` so a
  second call is a no-op).
  Effort: small-medium (about 1 day): 1 line in `CallMethodNode`, about 30
  lines in `DataModel`/`CompositeMethodNode`, about 60 in `FrostProtocolMng`,
  about 10 tests. Touches no YAML, no public node API.
  Risks: re-entrancy (resume runs inside the variable `write()` stack of the
  trigger; already true for top-level); the behavior change that a nested wait
  no longer emits the spurious update message (that message was a symptom;
  check no test relies on it); index entries must be dropped in
  `delete_context` and when a composite is removed from the model.
- **O2 - Node-side termination listener.** `CompositeMethodNode` keeps
  `set_termination_callback(ctx_id, cb)` invoked from `resume_execution` when a
  context becomes terminal; Frost registers one for each top-level context and
  answers/releases from the callback. P1 and P2 as in O1. Cleaner layering and
  it also fixes the release asymmetry for direct-API users, but it runs
  Frost code in the middle of the notify cascade (the callback deletes a
  context while grandparents are still unwinding) and adds a new public
  concept. Effort: medium (about 1.5 days).
- **O3 - Register nested contexts in `_running_methods`.** Composites call back
  into the manager when they create a child context. Needs the manager
  reference inside nodes (the model must not depend on the protocol layer);
  rejected.
- **O4 - Inline nested composites** (macro-expand the callee CFG into the
  caller). Changes semantics (separate contexts, return values, per-callee
  `requires`); rejected.
- **O5 - Forbid waits in nested composites** (reject at load, or document).
  Cheapest, but blocks the main use of phase 5 (`on_unmet: wait` on a method
  called from a composite that is itself called from another composite);
  acceptable only as a temporary limit.

### Recommendation

O1. Do it before phase 5, as its own PR ("phase 4.5"), because phase 5 adds
wait subscriptions and a deadline that are only checked on resume, and both
depend on the child actually being resumed. Keep O2 as a later refactor if the
release asymmetry matters outside Frost.

### Tests (O1)

1. The strict `xfail` test of the phase 3 review turns into a normal passing
   test (nested wait completes: one response to the original request, no
   contexts, no subscriptions, `_running_methods` empty).
2. Nested wait that ends in `FAILURE`: one error update with the request's
   correlation id, same cleanup.
3. Grandparent chain A -> B -> C with the wait in C: C resumed, B and A
   cascade, A answered exactly once.
4. Nested remote call: the response with the child's correlation id is routed
   to the child and the request finishes.
5. Duplicate trigger (two writes in a row): the second one is a no-op, no
   exception, no second response.
6. Direct-API path unchanged (no Frost, no data model index: composites work
   as before).
7. Phase 5 prerequisite: `on_unmet: wait` in a composite called from another
   composite completes over Frost.

## 12. Follow-up design: unexpected exceptions become FAILURE

Problem (limit 9.7): `ControlFlow.execute` calls `node.execute(context)` with no
protection. A programming or configuration error (`KeyError` for a missing
template value, `AssertionError`, an exception raised by a method callback,
a connector error) leaves the context active at the same pc. Callers see the
raw exception, or nothing at all when it happens inside a notification
cascade; the composite is neither completed nor failed, and what the failing
node owned (wait subscription, pending keys) leaks.

Design:

1. `ExecutionErrorCode.UNEXPECTED_ERROR = "unexpected_error"`.
2. In `ControlFlow.execute`, wrap `node.execute(context)` in `try/except
   Exception` (never `BaseException`: `KeyboardInterrupt`, `SystemExit` and
   `asyncio.CancelledError` keep propagating). On exception: log with traceback
   at ERROR level, build `ExecutionError(UNEXPECTED_ERROR,
   f"{type(exc).__name__}: {exc}", node=<qualified name>)` and treat it as a
   `FAILURE` of that node (`context.fail`, trace end, return the messages
   collected so far).
3. New hook `ControlFlowNode.release(context)`, default no-op, called
   best-effort (its own `try/except`, logged) on the failing node: the wait
   node removes its per-context subscription and keys, `CallMethodNode` removes
   its pending key and subscription (and deadline key from phase 5). This
   replaces "the node cleans up before returning FAILURE" for the case where
   the node never got to do it.
4. Frost: `UNEXPECTED_ERROR` -> `ErrorCode.UNKNOWN` with the generic text
   `ErrorMessages.UNEXPECTED_ERROR` and **no exception text** (it can carry
   paths, values and internals; the detail goes to the log together with the
   request correlation id). With option B of 4.H this is the `public_message=None`
   default.
5. Optional strict mode for development and tests: `ControlFlow(strict=True)`
   or a module switch that re-raises, so a failing test shows the traceback
   instead of an error result.

Behavior changes to accept explicitly: direct-API callers that today catch an
exception from a composite call (`pytest.raises(KeyError)` and similar) get a
`MethodExecutionResult` with `error` set instead; the existing tests that pin
raw exceptions are updated deliberately (list them with `grep -rn
"pytest.raises" tests/behavior tests/nodes/composite_method`). A nested parent
that hits an exception inside its own CFG during a child's notification ends
`FAILED` (consistent with 9.7) instead of staying stuck; the narrow
"parent context not found" catch in `_notify_nested_parent` stays.

Effort: small-medium (about 0.5-1 day): about 20 lines in `control_flow.py`, the
`release` hook in `WaitConditionNode` and `CallMethodNode` (about 30 lines),
enum value and Frost mapping, about 8 tests (exception in the first node, in a
node after a wait with the subscription removed, in a nested parent during a
child's resume, `BaseException` still propagates, strict mode, Frost response
carries no exception text).
Priority: medium. Not a blocker for phase 5; do it before production use,
because stuck contexts and leaked subscriptions are silent.
Open questions: strict mode as a constructor flag or a global switch; whether
`AssertionError` should be excluded (it normally marks a bug and is useful
when it propagates in development).
