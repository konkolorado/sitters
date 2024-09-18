import asyncio
import unittest.mock

from sitters import sit


async def test_function_with_timeout_actually_timesout():
    TIMEOUT = 2
    SLEEP = 5
    FULLY_RAN = False

    @sit(timeout=TIMEOUT)
    async def f():
        await asyncio.sleep(SLEEP)

        nonlocal FULLY_RAN
        FULLY_RAN = True
        return True

    result = await f()
    assert not FULLY_RAN
    assert result is None


async def test_function_with_timeout_that_completes_on_time_succeeds():
    TIMEOUT = 5
    SLEEP = 1
    FULLY_RAN = False

    @sit(timeout=TIMEOUT)
    async def f():
        await asyncio.sleep(SLEEP)

        nonlocal FULLY_RAN
        FULLY_RAN = True
        return True

    result = await f()
    assert FULLY_RAN
    assert result


async def test_timedout_function_calls_timeout_hooks():
    TIMEOUT = 1
    SLEEP = 5
    FULLY_RAN = False

    timeout_hook = unittest.mock.AsyncMock()

    @sit(timeout=TIMEOUT, timeout_hooks=[timeout_hook])
    async def f():
        await asyncio.sleep(SLEEP)

        nonlocal FULLY_RAN
        FULLY_RAN = True
        return True

    result = await f()
    assert FULLY_RAN is False
    assert result is None
    timeout_hook.assert_called_once()
    timeout_hook.assert_awaited_once()


async def test_non_timedout_function_does_not_call_timeout_hooks():
    TIMEOUT = 5
    SLEEP = 1
    FULLY_RAN = False

    timeout_hook = unittest.mock.AsyncMock()

    @sit(timeout=TIMEOUT, timeout_hooks=[timeout_hook])
    async def f():
        await asyncio.sleep(SLEEP)

        nonlocal FULLY_RAN
        FULLY_RAN = True
        return True

    result = await f()

    assert FULLY_RAN
    assert result
    timeout_hook.assert_not_awaited()
    timeout_hook.assert_not_called()


async def test_timedout_function_can_call_many_timeout_hooks():
    TIMEOUT = 1
    SLEEP = 5
    FULLY_RAN = False

    timeout_hooks = [
        unittest.mock.AsyncMock(),
        unittest.mock.AsyncMock(),
        unittest.mock.AsyncMock(),
        unittest.mock.AsyncMock(),
    ]

    @sit(timeout=TIMEOUT, timeout_hooks=timeout_hooks)
    async def f():
        await asyncio.sleep(SLEEP)

        nonlocal FULLY_RAN
        FULLY_RAN = True
        return True

    result = await f()

    assert not FULLY_RAN
    assert result is None
    for h in timeout_hooks:
        h.assert_called()
        h.assert_awaited()
