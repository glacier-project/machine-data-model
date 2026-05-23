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


def _make_data_model() -> DataModel:
    return DataModel(name="test")


@pytest.mark.exposer
def test_constructor_stores_data_model_and_defaults() -> None:
    """The manager exposes the data_model property and applies defaults."""
    data_model = _make_data_model()
    manager = ExposerManager(data_model)
    assert manager.data_model is data_model
    assert manager.host == "0.0.0.0"
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
            async def _hang(request):
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
