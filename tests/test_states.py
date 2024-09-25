import asyncio
import unittest.mock

import pytest

from sitters import get_this_sit, sit
from sitters.states import SitState


async def test_active_sit_is_in_correct_state():
    STATE = None
    EXPECTED = SitState.RUNNING

    @sit
    async def f():
        ctx = get_this_sit()

        nonlocal STATE
        STATE = ctx.state

    await f()

    assert STATE is not None
    assert STATE == EXPECTED


async def test_failed_sit_is_in_correct_state():
    STATE = None
    EXPECTED = SitState.FAILED

    async def failed_callback():
        ctx = get_this_sit()
        nonlocal STATE
        STATE = ctx.state

    m = unittest.mock.AsyncMock(side_effect=Exception)
    fn = sit(m, exception_hooks=[failed_callback])
    with pytest.raises(Exception):
        await fn()

    assert STATE is not None
    assert STATE == EXPECTED


async def test_timedout_sit_is_in_correct_state():
    STATE = None
    EXPECTED = SitState.CANCELLED

    async def timedout_callback():
        ctx = get_this_sit()

        nonlocal STATE
        STATE = ctx.state

    @sit(timeout_hooks=[timedout_callback], timeout=1)
    async def f():
        await asyncio.sleep(1)

    await f()

    assert STATE is not None
    assert STATE == EXPECTED


async def test_completed_sit_is_in_correct_state():
    STATE = None
    EXPECTED = SitState.COMPLETED

    async def completed_callback():
        ctx = get_this_sit()

        nonlocal STATE
        STATE = ctx.state

    m = unittest.mock.AsyncMock()
    await sit(m, completion_hooks=[completed_callback])()

    assert STATE is not None
    assert STATE == EXPECTED
