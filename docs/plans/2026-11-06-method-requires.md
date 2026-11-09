# Plan: `requires` (preconditions) on method nodes

Status: approved decisions (D1-D5, P1-P6); phases 1-3 implemented, reviewed and
committed (`34308ce` docs, `fabab64` feat). **Order of the remaining work:
phase 4.5 -> phase 4 -> phase 5** (section 7). Author: researcher.
Date: 2026-11-06. Revisions: 3 folded in the phase 2 review; 4 the phase 3 review
(terminal states are final, limits 9.5 and 9.6, section 11); **5 folds in an
independent adversarial review of the phase 4/4.5/5 proposals**: phase 4.5
corrected and extended (section 11), `received_at` instead of a write-based
timestamp (4.F), no authorization-based disclosure argument (4.H replaced),
load warning instead of load error for a missing `on_unmet` (P5), no `RLock`
(limit 9.8 replaced), section 12 needed by section 11. **Revision 6** records phase 4.5 as built (11.3, 11.4, 11.10), the shared-correlation-id limit (9.10), the claim-first note of 9.8 and the work breakdown of phase 4 (groups A, B, C).

Paths are relative to the repository root. Line numbers refer to `dev` and may
drift.

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
- `CallRemoteMethodNode` / `WaitRemoteEventNode` semantics (routing of remote
  Frost `ERROR` messages to the waiting context **is** in scope, phase 4.5,
  section 11.3);
- connection-state API on connectors;
- OPC UA `Executable` attribute exposure (the `is_executable()` helper is the
  hook for it).

## 2. Decisions (approved)

| Id | Decision |
|----|----------|
| D1 | `CallMethodNode` gets `on_unmet: wait \| fail`, with **no implicit default**. A missing `on_unmet` on a callee that has `requires` is a load **warning** (a strict mode raises) and a run-time `INVALID_CONFIGURATION` failure (P5). `wait` is an atomic attempt-call (no `WaitCondition` + call race). Optional `timeout`, checked on resume against a deadline stored in the context. |
| D2 | `ExecutionNodeResult.status` in `{SUCCESS, RUNNING, FAILURE}` plus optional `ExecutionError(code, message, node)`. `.success` stays (`== SUCCESS`). `execution_failure()` keeps meaning RUNNING. New `execution_error(...)`. Codes: `PRECONDITION_NOT_MET`, `NO_DATA`, `TIMEOUT`, room for remote errors. |
| D3 | `Condition` evaluates to `ok \| failed \| no_data`. `no_data` behaves like `failed` for flow but has a distinct code. Not configurable yet. |
| D4 | Field name `requires`: list of `{variable, operator, rhs}` mappings, AND semantics, no new YAML tag. Dumper emits it only when non-empty. Name `pre_call` is avoided (already an attribute). `MethodNode.__call__` never waits. Expose `evaluate_requires()` and `is_executable()`. |
| D5 | `requires` may reference method parameters. |

Decisions taken by this plan, approved by the user (see section 10):

- P1. Nodes that return `FAILURE` clean up their own subscriptions and context
  keys before returning, instead of the run loop doing it (the loop does not
  know which keys a node owns).
- P2. Callee not statically resolvable (templated path) and `on_unmet` missing:
  runtime `FAILURE` with code `INVALID_CONFIGURATION`, not a load error. Since
  P5 the same run-time rule applies to every callee, static or templated.
- P3. `requires` is evaluated with cached values (`force_remote_read=False`).
- P4. Remote callees (`CallRemoteMethodNode`) are untouched.
- P5 (revised by the adversarial review, approved). A `CallMethodNode` whose
  callee has `requires` and whose `on_unmet` is missing: **load warning**
  (module logger, naming composite, call index and callee; a strict-mode option,
  name to be chosen, raises `ValueError` instead) and, at run time, **always**
  `FAILURE(INVALID_CONFIGURATION)` before the call, whether the requires hold
  or not (deterministic, independent of data). A condition that cannot be
  evaluated for a static configuration reason (a remote variable without a
  connector) is `INVALID_CONFIGURATION` as well, never `NO_DATA`, never waited
  on (4.I).
- P6 (approved). Work order: phase 4.5 (nested contexts, remote `ERROR`
  routing, lost-wakeup and write fixes, section 11), then phase 4, then
  phase 5. Phase 4 makes remote rejections and nested waits normal, so 4.5 must
  exist first.

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
- `no_data` when: the value is `None`; a remote variable has never received a
  value (phase 4, item 4.F); the read fails with a connection-type error (phase
  4, item 4.G); the comparison raises `TypeError` (e.g. `None < 5`). A missing
  or non-variable node, and a remote variable without a connector, are **not**
  `no_data`: they raise `ConditionError` (configuration error, 4.I). Connection state
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
2. If the callee has `requires` and `on_unmet is None`: return
   `execution_error(INVALID_CONFIGURATION)` **before** calling, whether the
   requires hold or not (P5). Otherwise try the call. `MethodPreconditionError`
   caught:
   - code `INVALID_CONFIGURATION` -> `execution_error(...)` whatever `on_unmet`
     says (a configuration error is never waited on).
   - `on_unmet is fail` -> `execution_error(err.error)`.
   - `on_unmet is wait` -> deadline check (timeout), subscribe to
     `Condition.variables(...)` of the callee with the per-context
     subscription (same keys pattern as `WaitConditionNode`), return RUNNING.
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

### Phase 4.5 - Nested contexts, remote errors, wakeups, write fix (runs BEFORE phase 4)

Details, options and tests are in section 11. Summary: `DataModel.find_context`
index; Frost resolves subscriber and correlation ids through it; the root
context id is found **before** resuming and the request is finished
idempotently afterwards; remote Frost `ERROR` messages reach the waiting
context as `REMOTE_ERROR`; `notify_subscribers` iterates a copy and
subscriptions are deduplicated; `drain_update_messages()` replaces
`get_update_messages()` + `clear_update_messages()`; `delete_context` via
`pop`; remote write confirms before the cache changes.

### Phase 4 - `MethodNode.requires` and direct-call rejection

**Work breakdown (worker; recorded 2026-11-06).** Small commits, each reviewed
at the end of its group; group C depends on A and B.

- **Group A (condition and message groundwork).**
  - A1 one-line sanitize helper (collapse whitespace and control characters,
    cut, ellipsis), shared by the Frost detail truncation (4.H), the remote
    error text (11.3) and the bounded `observed` text.
  - A2 `Condition.resolve()` / `evaluate_on()` (4.A).
  - A3 observed value out of the message into `observed` fields (4.H).
  - A4 `ConnectionError`/`TimeoutError` around `read()` give `NO_DATA` (4.G).
  - A5 remote variable without a connector gives `ConditionError`
    (`INVALID_CONFIGURATION`) (4.I).
  - **Next review: end of group A.**
- **Group B (variable state).**
  - B1 `received_at` timestamp at the three origin sites (4.F).
  - B2 `NO_DATA` for a remote variable that never received a value (4.F).
  - B3 audit of connector read/write exceptions so that connection and
    timeout failures surface as `ConnectionError` / `TimeoutError` (4.G).
  - B4 `VariableNode.write()` skips the restore write when the variable never
    received a value (`received_at is None`): it would send the constructor
    default to the machine; log instead (4.F, restore-skip).
- **Group C (the feature).**
  - C1a `MethodNode.requires`, `MethodPreconditionError`, `_check_requires`;
    C1b `evaluate_requires()` / `is_executable()` and the construction check
    of `${name}` references (files 1 and 4.B).
  - C2 `CompositeMethodNode.requires` (does not call `super().__call__`).
  - C3 Frost mapping in `_invoke_method` (file 6 and 4.B).
  - C4 builder (file 3); C5 dumper and `__eq__` (files 4 and 5);
    C6 `DataModel` validation pass of static `requires` paths (4.C);
    C7 README (file 7).

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
2. `no_data`: variable `None`, remote variable that never received a value ->
   `NO_DATA` code, distinct from `PRECONDITION_NOT_MET`; a remote variable
   without a connector is `INVALID_CONFIGURATION` (4.I), not `NO_DATA`.
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
timestamp; revised by the adversarial review: it is `received_at`, with three
origin sites; safety relevant).**
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
really originates from the remote side. There are **three** such sites:

- `_remote_subscription_callback` (remote change);
- `subscribe_to_remote_changes`, the initial `connector.read_node_value` when
  its result is not `None`;
- the `force_remote_read=True` branch of `VariableNode._read_remote_value`
  (base class, which the subclasses call through `super()`) when the connector
  result is not `None`.

A successful remote **write is not a site** (dropped in revision 5): for MQTT
the publish topic can differ from the state topic, and a confirmed publish does
not prove that the state the variable mirrors has that value.

Options:

- **A. Boolean flag** set at the three sites; `has_received_value()` is `True`
  for local variables, the flag for remote ones. Smallest change. Cannot
  express staleness; never resets when the connection drops.
- **B. Timestamp (chosen).** `_received_at: float | None` (epoch seconds,
  `time.time()`) set at the three sites; `has_received_value()` = local
  variable, or `_received_at` is not `None`; exposes `received_at`.
  **Name and meaning:** this is the time the value *arrived in this process*,
  not the time the source produced it. A retained MQTT message or the initial
  read at start-up looks fresh. It proves "a value was received", never "the
  value is recent". A separate `source_timestamp` (OPC UA `SourceTimestamp`,
  MQTT payload time) is a later addition and the only basis for a `max_age`
  staleness guard.
- **C. Make unreceived reads return `None`.** Rejected: changes the public
  `read()` contract and the declared return types of every node.
- **D. Quality object** (`Good/Uncertain/Bad` + timestamps, OPC UA StatusCode
  style) carried by connectors' callbacks. Largest change (connector API and
  `SubscriptionArguments`); a later step on top of B.

Implemented in the base class (`machine_data_model/nodes/variable_node.py`),
with `Condition.evaluate_on` returning `NO_DATA` ("(no value received yet)")
for a remote variable whose `has_received_value()` is `False`.
`ObjectVariableNode`: received when every property is received (empty object:
`True`). Not in this phase: reset on disconnect (needs a connector hook such as
`mark_stale()`), `source_timestamp`, `max_age`. Tests: fake connector whose
initial read is `None` -> `NO_DATA`; after a subscription callback ->
`OK`/`FAILED`; after a forced read returning a value -> `OK`/`FAILED`; a
successful remote write does **not** set `received_at`; local variable always
has a value; a cached read of the default does not set it (regression for the
`read()` write-back); the same through `requires` on a method (call rejected
with `NO_DATA`) and `CallMethodNode` wait mode (stays RUNNING). The phase 2
test that pins today's weakness (guard passes on the default) is flipped by
this change.

4.F-restore **Restore write for a never-received variable (B4).**
`VariableNode.write()` restores the previous value with a second remote write
when `_post_update_value` rejects the update. For a remote variable that never
received a value the snapshot is the constructor default, which the machine
never had; writing it is a spurious write (probe: a rejected update sent
`[5, 0]`). Rule: if `received_at is None` skip the restore write, log an error
("cannot restore, previous value unknown") and restore only the cache. Tests:
never-received variable with a rejecting post hook -> exactly one remote write;
a received variable still restores.

4.G **Exceptions raised by `variable.read()` (DECIDED by the user: connection and
timeout errors -> `NO_DATA`, every other exception propagates, connector exception audit
included).** `Condition.evaluate`
catches `ConnectionError` and `TimeoutError` around the read (narrowed from
`OSError` in revision 7, group A review finding 6: `FileNotFoundError`,
`PermissionError` and `EMFILE` are also `OSError` but are configuration or
system faults, and with a phase 5 wait they would wait forever) and returns
`NO_DATA` with message "<text>: read failed (<type>)". Everything else
(`RuntimeError`, `AssertionError`, programming errors) propagates. With the
cached reads of P3 this is rare; it matters for `force_remote_read=True`
(phase 5, `WaitConditionNode`). Open sub-task: connector libraries raise their
own types (asyncua, aiomqtt); I did not audit them. Audit
`AbstractConnector.read_node_value` implementations and wrap connection/timeout
failures into `ConnectionError`/`TimeoutError` at the connector boundary, so
the `ConnectionError`/`TimeoutError` catch is sufficient. Tests: stub variable
whose read raises `ConnectionError`/`TimeoutError` -> `NO_DATA`;
`RuntimeError`/`FileNotFoundError`/`PermissionError` -> raises.

4.H **Frost boundary: detail text, observed values, size (REPLACED in
revision 5; user approved).** Since phase 3 the Frost error text is
`"<enum text>: <error.message>"`. From phase 4 on, `error.message` is built
from the condition. Decision:

- **One message, without the observed value.** `ConditionOutcome.message` and
  therefore `ExecutionError.message` say what must hold and what failed
  (`"/plant/conveyor/mode == 2 not met"`, `"/plant/conveyor/mode == 2: no value
  received yet"`), never the current value.
- **The observed value goes in a structured field**:
  `ConditionOutcome.observed: str | None` and `ExecutionError.observed:
  str | None` (a bounded `repr`, at most 256 characters), carried through
  `MethodPreconditionError` and `CallMethodNode._wrap_error` (like `origin`) and
  used by logs and traces. **It is never sent over Frost.**
- **Truncation at the Frost boundary**, needed with any message: one helper
  used by `_create_execution_error_message` collapses whitespace and control
  characters to single spaces, cuts the detail to 256 characters and appends
  `...`; cut on `str`, never on bytes; the enum text is never cut; the limit is
  a module constant. It can ship with the phase 3 fixes (the Frost detail path
  already exists).

Why not the earlier proposal (a separate `public_message`, default `None`
sending only the generic text): the Frost protocol has **no authorization**
(see limit 9.9: any caller can already `READ` any variable), so hiding the
observed value in the error text is cosmetic, and a `None` default would
regress the detail that phase 3 already sends. The structured `observed` field
keeps the diagnostic value for the operator without growing the remote text.

Tests: a 10 000-character detail is cut to the limit; newlines, tabs and
control characters never appear in the sent text; the observed value appears
in `error.observed` (and in the log/trace) but not in the Frost message;
a nested failure prefixes callee paths and keeps `observed`/`origin`; non-ASCII
text survives; a condition on a huge text variable produces a bounded
`observed`.

4.I **Static configuration problems are `INVALID_CONFIGURATION`, never
`NO_DATA` (P5).** `Condition.evaluate_on` raises `ConditionError` for a remote
variable without a connector (today it returns `NO_DATA`, phase 2 test
`test_no_data_for_remote_variable_without_connector` is flipped): the model
has nothing to wait for. `NO_DATA` stays for conditions that can change by
themselves (`None`, never received, read failed, uncomparable). Consumers: the
direct call rejects with `INVALID_CONFIGURATION`; `CallMethodNode` never waits
on it.

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

Note (limits 9.11, 9.12): a wait on a remote variable that never received a
value (a confirmed write does not count) gives `NO_DATA` until the connector
delivers a value, so with a connector that does not echo changes the wait only
ends through `timeout`; document this next to `on_unmet: wait`. The connector
error mapping it relies on is tested with mocks only.

Files / changes:

1. `behavior/local_execution_node.py`: `OnUnmet` enum; `CallMethodNode` new
   arguments `on_unmet`, `timeout`; `execute` per 4.4; cleanup helper shared
   with `WaitConditionNode` for the per-context subscription (key pattern
   unchanged so `test_wait_subscription_bug` keeps its meaning); `__eq__` and
   properties updated.
2. `data_model.py`: after `_register_nodes` and `_setup_inheritable_specs`
   (all nodes registered), a validation pass over every `CompositeMethodNode`
   CFG: for each `CallMethodNode` whose callee resolves statically to a
   `MethodNode` with non-empty `requires` and `on_unmet is None`, log a
   **warning** naming composite, call index and callee (P5); with the
   strict-mode option, raise `ValueError` instead. Run it inside the existing
   `try` so connectors are cleaned up on failure. At run time the node fails
   with `INVALID_CONFIGURATION` whenever `on_unmet` is missing and the callee
   has `requires` (4.4 step 2). Not applied to
   `CallRemoteMethodNode` (P4). The pass already exists from phase 4 (static
   `requires` paths, 4.C); this phase adds the `on_unmet` rule to it. In wait
   mode (G3, group A review finding 4) `Condition.resolve()` itself raises the
   same `ConditionError` as `evaluate_on` for a remote variable without a
   connector, so `variables()` and the evaluation agree and a wait never
   subscribes to a variable that evaluation later rejects. `Condition.resolve` is called once per attempt and its result feeds both
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
4. Load-time and run-time (P5): callee with `requires` and no `on_unmet` logs
   a warning at `DataModelBuilder` load with the composite and callee names
   (and raises in strict mode); callee without `requires` and no `on_unmet`
   loads silently; callee added later in YAML order still detected (validation
   runs after full registration); at run time the call fails with
   `INVALID_CONFIGURATION` whenever `on_unmet` is missing and the callee has
   `requires`, **also when the requires hold** and for a templated callee path
   (P2); a remote variable without a connector fails with
   `INVALID_CONFIGURATION` in both modes and is never waited on.
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

One PR per phase. Order: 1, 2, 3 (done), **4.5, 4, 5** (P6). Phases 1-2 are
pure refactor/tests (no behavior change) and can merge without product review.
Phase 3 is invisible to YAML users. Phase 4.5 fixes Frost routing and two
variable bugs (no YAML change). Phases 4 and 5 add the feature.

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
3. Remote Frost `ERROR` messages are dropped by
   `FrostProtocolMng.handle_message` and a `CallRemoteMethodNode` waits forever
   on them (until phase 4.5, section 11.3, which routes them to the waiting
   context as `REMOTE_ERROR`; revision 5 moved this from "follow-up" into
   phase 4.5 because phase 4 makes remote rejections normal).
4. `requires` are a permissive (checked when the call starts). Conditions that
   must keep holding while a composite runs (interlocks) are not modeled.
5. **[FIXED in phase 4.5, section 11] Nested composites that waited were never resumed under Frost (pre-existing,
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
6. **`resume_execution` does not release a terminal context** (the top-level answer/release part is FIXED in phase 4.5 by `_finish_if_terminated`; the contract for direct-API users stays) (only
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
8. **Composite state is not thread-safe, and a lock is not the answer**
   (pre-existing; revised in revision 5). Variable-change callbacks run on
   connector threads (`abstract_async_connector.py` runs an asyncio loop
   thread; OPC UA and MQTT callbacks call `notify_subscribers` there), while
   method invocations and Frost requests run on other threads.
   `CompositeMethodNode._contexts`, `_completed_results`,
   `_notified_parent_contexts` and `FrostProtocolMng._running_methods` are plain
   dicts; two concurrent resumes of the same context can execute a node twice.
   **No `RLock` in `FrostProtocolMng`**: callbacks run on the connector loop
   thread, and a locked method doing a remote read or write waits for that same
   loop, which is blocked on the lock: deadlock. Phase 4.5 only makes the
   individual operations safe (atomic `drain_update_messages()`,
   `delete_context` via `dict.pop`, copy-iteration in `notify_subscribers`).
   Follow-up, unscheduled: a **single executor thread owns all composite
   state**; connector callbacks and Frost handlers only enqueue
   `resume(ctx_id)` and never touch contexts. Contract until then: callers
   serialize resumes of one composite.
   **Claim-first note (review of phase 4.5):** when this limit is tackled,
   `FrostProtocolMng._finish_if_terminated` must take ownership of a request
   before looking at it: `entry = self._running_methods.pop(root_id, None)`, and
   put it back if the context is not terminal yet. With check-then-delete, two
   threads finishing the same request could both answer it (the completion and
   the "released elsewhere" error) and the second `del` raises `KeyError`. The
   worker applies the claim-first ordering already (E3) because it also removes
   the single-threaded double-delete hazard.
9. **The Frost protocol has no authorization** (known limit). Any caller can
   `READ`, `WRITE`, `SUBSCRIBE` and `INVOKE` any node. Consequences for this
   work: error texts cannot be "access controlled" (4.H does not try), and a
   remote caller can invoke methods whose `requires` expose model structure
   through the failing condition text. Out of scope here; an authorization
   layer would sit in `FrostProtocolMng` in front of every namespace handler.

10. **All remote requests of a context share one correlation id** (known
    limit, found in the phase 4.5 review). `CallRemoteMethodNode._create_request`
    and the other remote nodes use `correlation_id=context.id()`, and
    `ErrorPayload.node` is always empty. Consequences: a late or duplicated
    `ERROR` (or `RESPONSE`) for an earlier request of the same context is
    accepted as the answer of the next request in flight to the same remote
    (probe: `[remote_call, remote_call]`, stale `ERROR` for request 1 ends the
    request that waits for request 2); the same ambiguity exists for `RESPONSE`
    when the same node is called twice. Header checks (sender, target,
    namespace, msg_name, `payload.node` for responses) narrow it but cannot
    remove it. **Follow-up idea, protocol compatible:** a per-request
    correlation id, for example `f"{context.id()}:{pc}"`, used when sending, and
    a lookup that strips the suffix to find the context (the `find_context`
    index keeps the plain id) while `handle_response`/`handle_error` also
    require the exact id of the active request. Needs agreement with the FROST
    peers (they must echo the correlation id unchanged, which the protocol
    already requires). Not scheduled.

11. **A confirmed remote write is not a received value** (group B review,
    nit 4). `received_at` / `has_received_value()` only count values that
    arrived from the remote side (read, initial read, subscription callback).
    A remote variable that was written successfully but never received a
    value still gives `NO_DATA` ("no value received yet") on a cached read
    until the subscription echoes it. Every variable of a `DataModel`
    subscribes at construction, so the echo normally comes; with a connector
    that does not echo changes, an `on_unmet: wait` on such a variable waits
    forever (use `timeout`). Kept on purpose: the cache after a write is what
    we sent, not what the machine holds.

12. **Connector failure mapping is tested with mocks only** (B3 and H2: OPC UA
    status codes -> `ConnectionError`/`TimeoutError`, closed event loop ->
    `ConnectionError`). No live OPC UA server was used; the status-code list
    is a best effort and an unlisted transient code surfaces as
    `UNEXPECTED_ERROR` rather than `NO_DATA`.

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
   messages stay dropped (limit 9.3). **Superseded in part by revision 5:**
   the callee node stays untouched, but the remote `ERROR` routing itself is
   done in phase 4.5 (section 11.3).
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

Decided by the user for phase 4 (revision 5 changes marked):

8. "Has received a value": option B, a timestamp in the `VariableNode` base
   class, **renamed `received_at`, three origin sites, no write site** (4.F).
9. `read()` exceptions: `ConnectionError` and `TimeoutError` (narrowed from
   `OSError` in revision 7) -> `NO_DATA`; all other exceptions propagate; audit of connector exceptions is
   part of phase 4 (4.G).
10. The `DataModel` validation pass of static `requires` paths starts in phase 4
    (4.C), phase 5 extends it.
11. **Work order 4.5 -> 4 -> 5** and the revised phase 4.5 content (section 11):
    approved (P6).
12. **4.H replaced:** one message without the observed value, observed value in
    a structured field never sent over Frost, truncation to one line of 256
    characters; the `public_message` proposal is dropped (approved).
13. **P5:** missing `on_unmet` on a callee with `requires` is a load warning
    (strict mode raises) and a run-time `INVALID_CONFIGURATION` failure always;
    static configuration problems are never `NO_DATA` and never waited on
    (approved).
14. **No `RLock`** in `FrostProtocolMng`; limit 9.8 replaced (approved).

Also decided (manager, after the phase 4.5 reviews):

- Phase 4.5 review fixes E1 (namespace/msg_name check of remote errors), E2
  (remote text sanitized, code written by name) and E3 (claim-first pop in
  `_finish_if_terminated`, DEBUG log for non-error messages) are applied by the
  worker.
- The shared-correlation-id ambiguity is a documented limit (9.10); the
  per-request correlation id is a follow-up, not scheduled.
- Phase 4 is delivered in the groups A, B, C listed in the phase 4 work
  breakdown, with a review at the end of each group (next: group A).

Still open:

15. Should `on_unmet`/`timeout` also be accepted on `CallRemoteMethodNode`
    later, once remote `requires` can be discovered?
16. Follow-ups, not scheduled: `WaitConditionNode` through `evaluate_on` (4.A),
    disconnect hook, `source_timestamp` and `max_age`, quality object (option D
    of 4.F), unexpected exceptions become `FAILURE` (section 12; **required by
    section 11**, see there), single executor thread (limit 9.8), Frost
    authorization (limit 9.9).
17. Name of the strict-validation option of P5 (a `DataModel`/builder
    constructor flag).

## 11. Phase 4.5: nested composite contexts under Frost, remote errors, wakeups

Runs before phase 4 (P6). Revision 5: the first design (copy the parent's
subscription callback to the child; resume the child, then walk up to the root)
was wrong in two places, found by the adversarial review with probes, and the
scope grew by four related defects.

### 11.1 Problem (limit 9.5)

Only top-level composite contexts are registered in
`FrostProtocolMng._running_methods`; resumption triggers (variable change of a
wait subscription, remote response) carry the id of the context that is
actually waiting, which for a nested child is not registered. Facts:

- Wait subscription: `WaitConditionNode` creates
  `VariableSubscription(subscriber_id=context.id(), subscription_callback=
  context.get_subscription_callback())`. A nested child has no context
  callback, so the node-level callback installed by `ProtocolMng` runs:
  `_update_variable_callback`, which finds no match and emits an update message.
- Remote call: `CallRemoteMethodNode._create_request` uses
  `correlation_id=context.id()`; `handle_response` looks the id up in
  `_running_methods`.
- Resuming the parent does not drive the child: the pending branch of
  `CallMethodNode` only checks `is_terminated`. The existing up-cascade is
  child -> `_notify_nested_parent` -> parent `resume_execution`, so **the child
  itself must be resumed** and the cascade does the rest.
- After the cascade the root context may be terminal without Frost having
  been involved (limit 9.6): someone must answer the original request and
  release the context.

### 11.2 Design (O1, corrected)

1. **Do not copy the parent's subscription callback to the child.** The child
   context is created during the parent's first run, inside `method_node(*args)`;
   Frost sets the parent's callback only afterwards
   (`set_context_subscription_callback`, `frost_protocol_mng.py` ~410-418), so
   the copy would copy `None` (probe: scratchpad `probe1.py` of the review).
   Not needed: the node-level callback already runs for nested subscriptions.
2. **Context index.** `CompositeMethodNode._create_context` and
   `delete_context` (the only two sites; `delete_context` via `dict.pop` with a
   sentinel, raising `ContextNotFoundError`) register and unregister the id in
   `DataModel`: `DataModel.find_context(ctx_id) -> tuple[CompositeMethodNode,
   ExecutionContext] | None`, O(1); composites with no data model skip it.
   `_update_variable_callback` and `handle_response` (and the ERROR routing of
   11.3) resolve `subscriber_id` / `correlation_id` through it, then act on the
   owning composite.
3. **Find the root before resuming.** Walking up after the resume fails: the
   parent's `CallMethodNode` deletes the child context during the cascade
   (`local_execution_node.py` ~530), so the walk-up raises
   `ContextNotFoundError` (probe `probe2.py`). Therefore:
   `root_id = self._root_context_id(ctx_id)` (follow `__nested_parent_*` keys
   upward, across composites) **before** `owner.resume_execution(ctx_id)`; then
   `_finish_if_terminated(root_id)`.
4. **`_finish_if_terminated(root_id)`**: idempotent (keyed on presence in
   `_running_methods`); if the root context is terminal: build the completed or
   error response (`_create_execution_error_message`), `delete_context`, remove
   from `_running_methods`. It is the tail of today's
   `_resume_composite_method`, which now calls it too. Messages produced by
   the cascade are already in the resumed result (`_notify_nested_parent`
   extends them) and are appended to `_update_messages`.

### 11.3 Remote Frost `ERROR` messages reach the waiting context (as built)

Before: `FrostProtocolMng.handle_message` asserted an `ErrorPayload` and dropped
the message, so a composite waiting for a remote response hung. Phase 4 makes
remote rejections (a remote method with its own `requires` answering
`NOT_ALLOWED`) a normal event, so the error is routed. What was built:

- **Entry.** `handle_message` sends every message that is neither a request nor
  a response to `FrostProtocolMng.handle_error(msg)`. A message without an
  `ErrorPayload` is ignored (DEBUG log, E3; it was WARNING, which let an
  unauthenticated peer flood the log). The owner is found with
  `_owner_of_context(msg.correlation_id)` (context index first, then
  `_running_methods`); an unknown id is ignored and logged at DEBUG. The root
  context id is computed **before** the owner acts (as in 11.2 item 3).
- **Placement of the logic.** `FrostProtocolMng.handle_error` ->
  `CompositeMethodNode.handle_error(context_id, msg)` (only if the node the
  context waits on is a `RemoteExecutionNode`; terminal contexts are ignored
  because `get_current_node` returns `None`) ->
  `RemoteExecutionNode.handle_error(context, msg)` returning an
  `ExecutionError` or `None`.
- **Validation in `RemoteExecutionNode.handle_error`:** header type `ERROR`;
  `ErrorPayload`; `correlation_id == context.active_request`; `sender` is the
  resolved remote id; `target` is this node's `sender_id`; and (E1, review
  finding) `namespace` and `msg_name` equal the kind of request the node sent
  (`METHOD/INVOKE` for `CallRemoteMethodNode`, `VARIABLE/READ`, `/WRITE`,
  `/SUBSCRIBE` for the variable nodes) because `build_error_message` copies
  them from the request header. `payload.node` cannot be compared (always
  empty). Anything else is ignored: stale, duplicate, foreign.
- **Effect.** `context.fail(ExecutionError(REMOTE_ERROR, ...))`,
  `_terminate_execution`, `_notify_nested_parent`, returning a
  `MethodExecutionResult(messages, {}, error)`. Frost appends the cascade
  messages to `_update_messages` and calls the idempotent
  `_finish_if_terminated(root_id)` (also in an `except` branch that answers the
  request before re-raising).
- **`REMOTE_ERROR` without detail.** It is in `_ERRORS_WITHOUT_DETAIL`: the
  client of the original request gets `ErrorCode.UNKNOWN` plus
  `ErrorMessages.REMOTE_ERROR` only. The remote text is remote-controlled, so
  it is only logged, and (E2) it is collapsed to one line (whitespace and
  control characters removed, which prevents log forging), cut to 200
  characters, and the remote code is written by name.
- **A rejected `WaitRemoteEventNode` subscription** fails the context through
  `context.fail`, which clears `active_request`, so no unsubscribe is sent for a
  subscription the remote never accepted (tested).
- **Release messages (C1).** `ControlFlowNode.release(context)` now returns
  `list[FrostMessage]`: `RemoteExecutionNode.release` returns the node's cleanup
  message (for example the unsubscribe of a remote event wait) when its request
  is in flight or its response was received and not cleaned up yet, and nothing
  otherwise (no double cleanup); `CallMethodNode.release` and
  `CompositeMethodNode.abort_context` return the messages of the aborted child
  chain; `ControlFlow._execute_node` adds them to the failure result.
  `FrostProtocolMng._invoke_method` forwards `ret.messages` before every branch
  (completed, failed, running), not only for running requests, so messages
  produced by a call that ends immediately are no longer dropped.
- **Known limit:** requests of one context share a correlation id (limit 9.10).

### 11.4 Lost wakeups and duplicate subscriptions (as built)

`VariableNode.notify_subscribers` iterated the live `self._subscriptions`
while the resumes it triggers call `unsubscribe`: with three waiters on one
variable and one write an element was skipped and one waiter stayed stuck.

- `notify_subscribers` iterates `list(self._subscriptions)`.
- **Dedupe is scoped to wait subscriptions (deviation from the first design).**
  `VariableNode.subscribe` already dedups by `(subscriber_id, correlation_id)`.
  A generic "one subscription per subscriber" would break Frost clients that
  hold two `SUBSCRIBE` requests with different correlation ids on one variable.
  Instead `VariableNode.find_subscription_by_subscriber(subscriber_id)` exists
  and `WaitConditionNode` adopts a subscription its context already has on that
  variable instead of adding a second one, so one write wakes a context once.
  For phase 5 multi-variable waits: one subscription per variable, found by
  subscriber on each variable; never share one subscription object across
  variables unless unsubscribed per variable. Nit left: the adopted
  subscription does not receive the context callback patch (the node-level Frost
  callback still routes by `subscriber_id`).
- Tests: three waiters, one write, all three resume (also through three Frost
  requests on one nested chain); unsubscribe during notification does not skip.

### 11.5 Safe concurrency fixes (no lock, see limit 9.8)

- `FrostProtocolMng.drain_update_messages()`: atomically swaps the list
  (`messages, self._update_messages = self._update_messages, []`) and returns
  the old one. `get_update_messages()` returns the live list today, which races
  with `clear_update_messages()` (messages lost between the two calls). Keep the
  old methods, document them as unsafe, and move internal callers and tests to
  the new one.
- `CompositeMethodNode.delete_context` via `dict.pop` with a sentinel
  (atomic under the GIL), raising `ContextNotFoundError`; `_notify_nested_parent`
  keeps its pre-check and additionally tolerates a `ContextNotFoundError` whose
  id is the parent's.

### 11.6 Pre-existing bug: remote write confirms before caching

`VariableNode._update_value` (`variable_node.py` ~430) writes the cache first
(`_update_internal_value(value)`) and then calls `_update_remote_value`, which
reads `prev_value` from the **already updated** cache. A failed remote write
therefore returns the new value as "previous", `write()` reports success and
notifies subscribers of an unconfirmed value (probe `probe3.py`); a guard
reading the cache then sees a value the machine never accepted.

Fix: for remote variables with a connector, perform the remote write first;
update the cache and notify only when it is confirmed; on failure leave the
cache unchanged, `write()` returns `False`, no notification. Keep the
`_pre_update_value` / `_post_update_value` hooks and the existing
"`_post_update_value` returns `False` restores the previous value" behavior.
Tests: failing connector write -> `write()` is `False`, `read(False)` is the old
value, no subscriber called; successful write unchanged; local variables
unchanged.

### 11.7 Dependency on section 12

If a node raises while a nested cascade runs (`_notify_nested_parent` no longer
swallows it), the exception propagates out of the Frost callback and the root
request is never answered, its context and subscriptions stay. Section 12
(unexpected exceptions become `FAILURE`) is therefore **required** for this
phase to be end-to-end safe: either it lands first, or 4.5 includes at least
the `ControlFlow.execute` conversion (11.2 item 3 then always finds a failed
root to finish).

### 11.8 Effort, risks

Effort: about 2-3 days (index and Frost routing about 1, ERROR routing about
0.5, notify/dedupe/drain/pop fixes about 0.5, remote write fix about 0.5, tests
about 0.5-1, plus section 12 if bundled). Touches no YAML and no public node
API except the new `DataModel.find_context`, `CompositeMethodNode.handle_error`
and `drain_update_messages`.
Risks: re-entrancy (resume runs inside the trigger's `write()` stack, already
true for top-level); a nested wait no longer emits the spurious update message
(check no test relies on it); index entries must be removed in
`delete_context` and when a composite leaves the model; the write fix changes
`write()` results for failing remote writes (callers that ignored the return
value now see `False`).

### 11.9 Tests

1. The strict `xfail` test of the phase 3 review becomes a normal passing test
   (nested wait completes: one response, no contexts, no subscriptions,
   `_running_methods` empty).
2. Nested wait that ends in `FAILURE`: one error update with the request's
   correlation id, same cleanup.
3. Grandparent chain A -> B -> C with the wait in C: the root id is computed
   before the resume, B and A cascade, A is answered exactly once, the cascade
   deleting the child context does not break `_finish_if_terminated`.
4. Nested remote call: the response with the child's correlation id is routed
   to the child; a Frost `ERROR` with the child's correlation id fails the
   child with `REMOTE_ERROR` and the request ends with an error response; an
   `ERROR` with an unknown correlation id is ignored.
5. Duplicate trigger (two writes in a row): the second is a no-op, no
   exception, no second response.
6. Direct-API path unchanged (no Frost, no index: composites work as before).
7. Wakeup fixes of 11.4 and the drain/pop fixes of 11.5.
8. Remote write fix of 11.6.
9. Phase 5 prerequisite: `on_unmet: wait` in a composite called from another
   composite completes over Frost.

### 11.10 Other things built in phase 4.5 (additions and deviations)

- `ControlFlow.strict` is resolved at execution time (`ControlFlow.default_strict`,
  `tests/conftest.py` makes the suite strict); `ControlFlow._execute_node`
  converts `Exception` into `UNEXPECTED_ERROR`, then calls
  `node.release(context)` best effort (section 12 as built).
- Terminal states are final: `ExecutionContext.fail()` accepts only an active
  context, `reject_completion()` turns a just-completed context into a failed
  one (return value never set, completion hook raised: R1), `deactivate()` is a
  no-op unless active, `ControlFlow.execute` stops when a node ended its own
  context re-entrantly.
- Request answers: a request whose root context was released elsewhere is
  answered with a generic `UNEXPECTED_ERROR` (R2, warning logged); hooks
  failing during completion no longer escape into the writer of a trigger.
- DataModel context index: `register_context`, `unregister_context`,
  `find_context`; `CompositeMethodNode._create_context` and `_drop_context`
  maintain it (limits documented in the docstring).
- Remote writes: `_write_remote(value) -> bool` first, cache only after
  confirmation; `_snapshot` / `_restore` / `_remote_value` (numerics keep the
  raw value so offset units round-trip exactly); object writes validate the
  property set first and roll back only confirmed properties in reverse order;
  cached reads no longer write back (unit drift, getter domain unchanged,
  issue #67); `__init_subclass__` warns for removed hooks, mixins included.
- Frost: `drain_update_messages()` (atomic swap; `get_update_messages` /
  `clear_update_messages` documented unsafe, not deprecated).
- Not done in 4.5: deprecation of `get`/`clear`; test 7/9 of 11.9
  (`on_unmet: wait` nested over Frost) belongs to phase 5.

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
   request correlation id), consistent with 4.H.
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
Priority: raised in revision 5. It is **required by phase 4.5** (section
11.7): without it an exception raised during a nested cascade leaves the root
request unanswered, and the root `FAILED` state that `_finish_if_terminated`
relies on never exists. Land it before 4.5, or include the `ControlFlow.execute`
conversion and the `release` hook in 4.5.
Open questions: strict mode as a constructor flag or a global switch; whether
`AssertionError` should be excluded (it normally marks a bug and is useful
when it propagates in development).
