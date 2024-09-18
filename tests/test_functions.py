import unittest.mock

from sitters import sit


async def test_functions_are_run():
    m = unittest.mock.AsyncMock()
    await sit(m)()

    m.assert_called_once()
    m.assert_awaited_once()


async def test_nested_runs():
    EXPECTED_RESULT = "g"
    m = unittest.mock.AsyncMock(return_value=EXPECTED_RESULT)
    g = sit(m)

    @sit()
    async def f():
        return await g()

    result = await f()

    assert result == EXPECTED_RESULT
    m.assert_called_once()
    m.assert_awaited_once()
