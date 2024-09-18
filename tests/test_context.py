import unittest.mock

import pytest

from sitters import SitContext, get_this_sit, sit


async def test_sit_ctx_available_in_callbacks():
    RESULT = None

    m = unittest.mock.AsyncMock(name="GetSat")

    async def callback():
        nonlocal RESULT
        RESULT = get_this_sit()

    await sit(m, startup_hooks=[callback])()

    assert RESULT is not None
    assert isinstance(RESULT, SitContext)


async def test_sit_ctx_available_in_called_functions():
    SYNC_INTERIOR_SIT, ASYNC_INTERIOR_SIT = None, None

    def sync():
        nonlocal SYNC_INTERIOR_SIT
        SYNC_INTERIOR_SIT = get_this_sit()

    async def async_():
        nonlocal ASYNC_INTERIOR_SIT
        ASYNC_INTERIOR_SIT = get_this_sit()

    @sit()
    async def f():
        sync()
        await async_()

    await f()

    assert SYNC_INTERIOR_SIT is not None
    assert ASYNC_INTERIOR_SIT is not None
    assert isinstance(SYNC_INTERIOR_SIT, SitContext)
    assert isinstance(ASYNC_INTERIOR_SIT, SitContext)
    assert ASYNC_INTERIOR_SIT == SYNC_INTERIOR_SIT


async def test_sit_ctx_unavailable_outside_of_sits():
    with pytest.raises(RuntimeError):
        get_this_sit()


async def test_nested_sits_aquire_new_sit_ctx():
    PARENT_SIT, NESTED_SIT = None, None

    @sit()
    async def f():
        nonlocal PARENT_SIT
        PARENT_SIT = get_this_sit()
        await g()

    @sit()
    async def g():
        nonlocal NESTED_SIT
        NESTED_SIT = get_this_sit()

    await f()

    assert PARENT_SIT is not None
    assert NESTED_SIT is not None
    assert isinstance(PARENT_SIT, SitContext)
    assert isinstance(NESTED_SIT, SitContext)
    assert NESTED_SIT != PARENT_SIT
