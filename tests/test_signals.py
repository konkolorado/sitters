import contextlib
import signal
import typing as t
import unittest.mock

import anyio
import pytest

from sitters import sit


def _create_async_iterator_with(*values: signal.Signals):
    @contextlib.contextmanager
    def _asyncly_iterate(*args, **kwargs):
        yield AsyncIterator(values)

    return _asyncly_iterate


class AsyncIterator:
    def __init__(self, value: t.Any):
        self.iter = iter(value)

    def __aiter__(self):
        return self

    async def __anext__(self):
        # simulate a delay in generated signals so that the main tasks have an
        # opportunity to run
        await anyio.sleep(0.05)
        try:
            return next(self.iter)
        except StopIteration:
            raise StopAsyncIteration


async def test_sighup_restarts_sitting():
    RESULT = 100
    COMPLETIONS = 0

    async def _sleep_set_and_return():
        await anyio.sleep(1)
        nonlocal COMPLETIONS
        COMPLETIONS += 1
        return RESULT

    m = unittest.mock.AsyncMock(side_effect=_sleep_set_and_return)
    fn = sit(m)

    with unittest.mock.patch(
        "sitters.sitter.anyio.open_signal_receiver",
        _create_async_iterator_with(signal.SIGHUP),
    ):
        result = await fn()

    assert m.call_count == 2
    assert result == RESULT
    assert COMPLETIONS == 1


async def test_multiple_sighups_can_succeed():
    RESULT = 100
    COMPLETIONS = 0

    async def _sleep_set_and_return():
        await anyio.sleep(1)
        nonlocal COMPLETIONS
        COMPLETIONS += 1
        return RESULT

    m = unittest.mock.AsyncMock(side_effect=_sleep_set_and_return)
    fn = sit(m)

    signals = [signal.SIGHUP] * 5
    with unittest.mock.patch(
        "sitters.sitter.anyio.open_signal_receiver",
        _create_async_iterator_with(*signals),
    ):
        result = await fn()

    assert m.call_count == 1 + len(signals)
    assert result == RESULT
    assert COMPLETIONS == 1


@pytest.mark.parametrize("signal", [signal.SIGTERM, signal.SIGINT, signal.SIGKILL])
async def test_cancel_signals_cancel_sitting(signal: signal.Signals):
    COMPLETIONS = 0

    async def _sleep_set_and_return():
        await anyio.sleep(1)
        nonlocal COMPLETIONS
        COMPLETIONS += 1
        return True

    m = unittest.mock.AsyncMock(side_effect=_sleep_set_and_return)
    fn = sit(m)

    with unittest.mock.patch(
        "sitters.sitter.anyio.open_signal_receiver", _create_async_iterator_with(signal)
    ):
        result = await fn()

    assert m.call_count == 1
    assert result is None
    assert COMPLETIONS == 0


@pytest.mark.parametrize("signal", [signal.SIGTERM, signal.SIGINT, signal.SIGKILL])
async def test_cancel_signals_run_cancellation_hooks(signal: signal.Signals):
    hooks = [unittest.mock.AsyncMock(), unittest.mock.AsyncMock()]

    COMPLETIONS = 0

    async def _sleep_set_and_return():
        await anyio.sleep(1)
        nonlocal COMPLETIONS
        COMPLETIONS += 1
        return True

    m = unittest.mock.AsyncMock(side_effect=_sleep_set_and_return)
    fn = sit(m, cancellation_hooks=hooks)

    with unittest.mock.patch(
        "sitters.sitter.anyio.open_signal_receiver", _create_async_iterator_with(signal)
    ):
        result = await fn()

    assert m.call_count == 1
    assert result is None
    assert COMPLETIONS == 0
    for h in hooks:
        h.assert_called_once()
        h.assert_awaited_once()


async def test_sighup_runs_restart_hooks():
    hooks = [unittest.mock.AsyncMock(), unittest.mock.AsyncMock()]

    COMPLETIONS = 0

    async def _sleep_set_and_return():
        await anyio.sleep(1)
        nonlocal COMPLETIONS
        COMPLETIONS += 1
        return True

    m = unittest.mock.AsyncMock(side_effect=_sleep_set_and_return)
    fn = sit(m, restart_hooks=hooks)

    with unittest.mock.patch(
        "sitters.sitter.anyio.open_signal_receiver",
        _create_async_iterator_with(signal.SIGHUP),
    ):
        result = await fn()

    assert m.call_count == 2
    assert result is True
    assert COMPLETIONS == 1
    for h in hooks:
        h.assert_called_once()
        h.assert_awaited_once()


async def test_sighup_only_runs_restart_and_completion_hooks():
    restart_hooks = [unittest.mock.AsyncMock(), unittest.mock.AsyncMock()]
    completion_hooks = [unittest.mock.AsyncMock(), unittest.mock.AsyncMock()]
    other_hooks = [unittest.mock.AsyncMock(), unittest.mock.AsyncMock()]

    async def _sleep_set_and_return():
        await anyio.sleep(1)
        return True

    m = unittest.mock.AsyncMock(side_effect=_sleep_set_and_return)
    fn = sit(
        m,
        cancellation_hooks=other_hooks,
        restart_hooks=restart_hooks,
        completion_hooks=completion_hooks,
        exception_hooks=other_hooks,
        timeout_hooks=other_hooks,
    )

    with unittest.mock.patch(
        "sitters.sitter.anyio.open_signal_receiver",
        _create_async_iterator_with(signal.SIGHUP),
    ):
        result = await fn()

    assert m.call_count == 2
    assert result is True
    for h in restart_hooks:
        h.assert_called_once()
        h.assert_awaited_once()

    for h in completion_hooks:
        h.assert_called_once()
        h.assert_awaited_once()

    for h in other_hooks:
        h.assert_not_called()
        h.assert_not_awaited()


@pytest.mark.parametrize("signal", [signal.SIGTERM, signal.SIGINT, signal.SIGKILL])
async def test_cancel_signals_only_run_cancellation_hooks(signal: signal.Signals):
    hooks = [unittest.mock.AsyncMock(), unittest.mock.AsyncMock()]
    other_hooks = [unittest.mock.AsyncMock(), unittest.mock.AsyncMock()]

    async def _sleep_set_and_return():
        await anyio.sleep(1)
        return True

    m = unittest.mock.AsyncMock(side_effect=_sleep_set_and_return)
    fn = sit(
        m,
        cancellation_hooks=hooks,
        restart_hooks=other_hooks,
        completion_hooks=other_hooks,
        exception_hooks=other_hooks,
        timeout_hooks=other_hooks,
    )

    with unittest.mock.patch(
        "sitters.sitter.anyio.open_signal_receiver", _create_async_iterator_with(signal)
    ):
        result = await fn()

    assert m.call_count == 1
    assert result is None
    for h in hooks:
        h.assert_called_once()
        h.assert_awaited_once()

    for h in other_hooks:
        h.assert_not_called()
        h.assert_not_awaited()
