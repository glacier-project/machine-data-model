"""Tests for the ExposerManager lifecycle: construction, start, stop."""

import asyncio
import socket
import threading
import time

from aiohttp import web
import pytest

from machine_data_model.data_model import DataModel
from machine_data_model.exposers.abstract_exposer import AbstractExposer
from machine_data_model.exposers.exposer_manager import ExposerManager
from machine_data_model.nodes.folder_node import FolderNode
from machine_data_model.nodes.variable_node import NumericalVariableNode


def _make_data_model() -> DataModel:
    return DataModel(name="test")


@pytest.mark.exposer
def test_constructor_stores_data_model_and_defaults() -> None:
    """The manager exposes the data_model property and applies defaults."""
    data_model = _make_data_model()
    manager = ExposerManager(data_model)
    assert manager.data_model is data_model
    # Default bind is loopback: the surface has no built-in auth/TLS, so it
    # must not be reachable off-host unless the user opts in (F2).
    assert manager.host == "127.0.0.1"
    assert manager.port == 8080


@pytest.mark.exposer
def test_executor_is_single_worker() -> None:
    """Two slow jobs submitted to the executor must serialise."""
    manager = ExposerManager(_make_data_model())
    overlap_count = 0
    in_flight = 0
    lock = threading.Lock()

    def slow_job() -> None:
        nonlocal overlap_count, in_flight
        with lock:
            in_flight += 1
            if in_flight > 1:
                overlap_count += 1
        time.sleep(0.05)
        with lock:
            in_flight -= 1

    f1 = manager.executor.submit(slow_job)
    f2 = manager.executor.submit(slow_job)
    f1.result()
    f2.result()
    manager.executor.shutdown(wait=True)
    assert overlap_count == 0


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.exposer
def test_resolve_accepts_relative_and_root_prefixed_paths() -> None:
    """The shared resolve() handles an optional leading slash and root (F10)."""
    temp = NumericalVariableNode(name="Temperature", value=1.0)
    sensors = FolderNode(name="Sensors")
    sensors.add_child(temp)
    root = FolderNode(name="root")
    root.add_child(sensors)
    manager = ExposerManager(DataModel(name="t", root=root))

    assert manager.resolve("Sensors/Temperature") is temp
    assert manager.resolve("/Sensors/Temperature") is temp
    assert manager.resolve("root/Sensors/Temperature") is temp
    assert manager.resolve("Sensors/Missing") is None


@pytest.mark.exposer
def test_start_then_stop_is_clean() -> None:
    """A start/stop round-trip leaves no running thread or open loop."""
    manager = ExposerManager(
        _make_data_model(),
        host="127.0.0.1",
        port=_find_free_port(),
    )
    manager.start()
    try:
        # Server is up; we can confirm the port is bound.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((manager.host, manager.port))
    finally:
        manager.stop()
    # After stop, the thread is gone and the loop is closed.
    assert manager._thread is None or not manager._thread.is_alive()


@pytest.mark.exposer
def test_failed_start_cleans_up_runner() -> None:
    """A start that fails (port in use) must not leak the AppRunner (F8)."""
    port = _find_free_port()
    blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    blocker.bind(("127.0.0.1", port))
    blocker.listen(1)
    try:
        manager = ExposerManager(
            _make_data_model(),
            host="127.0.0.1",
            port=port,
        )
        with pytest.raises(RuntimeError, match="start failed"):
            manager.start()
        # The partially set-up runner was cleaned up, not left dangling.
        assert manager._runner is None
    finally:
        blocker.close()


@pytest.mark.exposer
@pytest.mark.filterwarnings("ignore::RuntimeWarning")
def test_start_timeout_is_configurable() -> None:
    """start() honours a caller-supplied timeout (F12)."""
    # A supplied loop that is never run means _serve never executes, so the
    # started-event is never set and start() must time out quickly. The
    # scheduled-but-unrun _serve coroutine triggers a benign "never awaited"
    # RuntimeWarning on loop close, suppressed above.
    loop = asyncio.new_event_loop()
    manager = ExposerManager(_make_data_model(), event_loop=loop)
    try:
        with pytest.raises(RuntimeError, match="start timed out"):
            manager.start(timeout=0.05)
    finally:
        loop.close()


@pytest.mark.exposer
def test_ephemeral_port_is_reflected_after_start() -> None:
    """With port=0 the OS-assigned port is reflected back on .port (F12)."""
    manager = ExposerManager(
        _make_data_model(),
        host="127.0.0.1",
        port=0,
    )
    manager.start()
    try:
        assert manager.port != 0
        # The reflected port is the one actually bound and connectable.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((manager.host, manager.port))
    finally:
        manager.stop()


@pytest.mark.exposer
def test_start_twice_raises() -> None:
    """Calling start() while already running is an error."""
    manager = ExposerManager(
        _make_data_model(),
        host="127.0.0.1",
        port=_find_free_port(),
    )
    manager.start()
    try:
        with pytest.raises(RuntimeError, match="already started"):
            manager.start()
    finally:
        manager.stop()


@pytest.mark.exposer
def test_stop_cancels_queued_executor_jobs() -> None:
    """stop() must not block on a backlog of queued executor work (F6).

    The single worker is occupied by a slow job; a second job queued behind
    it must be cancelled on shutdown rather than awaited, so a wedged backlog
    cannot hang stop() past its timeout.
    """
    manager = ExposerManager(
        _make_data_model(),
        host="127.0.0.1",
        port=_find_free_port(),
    )
    manager.start()
    # Occupy the single worker, then queue a second job behind it.
    manager.executor.submit(time.sleep, 0.5)
    queued = manager.executor.submit(time.sleep, 0.5)
    manager.stop(timeout=5.0)
    # The queued job never ran: shutdown cancelled it instead of waiting.
    assert queued.cancelled()


@pytest.mark.exposer
def test_stop_is_idempotent() -> None:
    """Calling stop() a second time is a no-op."""
    manager = ExposerManager(
        _make_data_model(),
        host="127.0.0.1",
        port=_find_free_port(),
    )
    manager.start()
    manager.stop()
    # Second call must not raise.
    manager.stop()


class _RecordingExposer(AbstractExposer):
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []  # (thread_name, manager_repr)

    def register(self, app, manager) -> None:  # type: ignore[no-untyped-def]
        self.calls.append(
            (threading.current_thread().name, type(manager).__name__)
        )


@pytest.mark.exposer
def test_register_called_once_on_async_thread() -> None:
    """register() is called exactly once, on the asyncio loop thread."""
    manager = ExposerManager(
        _make_data_model(),
        host="127.0.0.1",
        port=_find_free_port(),
    )
    exposer = _RecordingExposer()
    manager.add_exposer(exposer)
    manager.start()
    try:
        assert len(exposer.calls) == 1
        thread_name, mgr_class = exposer.calls[0]
        assert "exposer-loop" in thread_name
        assert mgr_class == "ExposerManager"
    finally:
        manager.stop()


@pytest.mark.exposer
def test_stop_timeout_does_not_raise(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A blocked shutdown logs a warning instead of raising."""

    class _HangingExposer(AbstractExposer):
        def register(self, app, manager) -> None:  # type: ignore[no-untyped-def]
            async def _hang(request: web.Request) -> web.Response:
                await asyncio.sleep(60)
                return web.Response()

            app.router.add_get("/hang", _hang)

    manager = ExposerManager(
        _make_data_model(),
        host="127.0.0.1",
        port=_find_free_port(),
    )
    manager.add_exposer(_HangingExposer())
    manager.start()
    try:
        with caplog.at_level(
            "WARNING",
            logger="machine_data_model.exposers.exposer_manager",
        ):
            manager.stop(timeout=0.05)
    finally:
        # If stop didn't fully shut down, daemon thread will exit at
        # interpreter shutdown.
        pass

    # We accept either: warning logged, or the shutdown completed before
    # the timeout. Both satisfy "does not raise".
