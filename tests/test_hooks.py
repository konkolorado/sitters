import asyncio
import unittest.mock

import pytest

from sitters import sit


async def test_all_hooks_run_on_failure():
    hooks = [
        unittest.mock.AsyncMock(),
        unittest.mock.AsyncMock(),
        unittest.mock.AsyncMock(),
        unittest.mock.AsyncMock(),
    ]

    m = unittest.mock.AsyncMock(side_effect=Exception)
    fn = sit(m, exception_hooks=hooks)

    with pytest.raises(Exception):
        await fn()

    for h in hooks:
        h.assert_called_once()
        h.assert_awaited_once()


async def test_all_hooks_run_on_success():
    hooks = [
        unittest.mock.AsyncMock(),
        unittest.mock.AsyncMock(),
        unittest.mock.AsyncMock(),
        unittest.mock.AsyncMock(),
    ]

    m = unittest.mock.AsyncMock()
    await sit(m, completion_hooks=hooks)()

    for h in hooks:
        h.assert_called_once()
        h.assert_awaited_once()


async def test_all_hooks_run_on_startup():
    hooks = [
        unittest.mock.AsyncMock(),
        unittest.mock.AsyncMock(),
        unittest.mock.AsyncMock(),
        unittest.mock.AsyncMock(),
    ]

    m = unittest.mock.AsyncMock()
    await sit(m, startup_hooks=hooks)()

    for h in hooks:
        h.assert_called_once()
        h.assert_awaited_once()


async def test_all_hooks_run_on_timeouts():
    FULLY_RAN = False
    hooks = [
        unittest.mock.AsyncMock(),
        unittest.mock.AsyncMock(),
        unittest.mock.AsyncMock(),
        unittest.mock.AsyncMock(),
    ]

    @sit(timeout=1, timeout_hooks=hooks)
    async def f():
        await asyncio.sleep(5)

        nonlocal FULLY_RAN
        FULLY_RAN = True
        return True

    await f()

    assert FULLY_RAN is False
    for h in hooks:
        h.assert_called_once()
        h.assert_awaited_once()
