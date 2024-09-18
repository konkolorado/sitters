import unittest.mock

from tenacity import retry, stop_after_attempt

from sitters import sit


async def test_retries_on_fn_that_always_fails():
    N_RUNS = 5

    m = unittest.mock.AsyncMock(side_effect=Exception)
    result = await sit(m, retry=retry(stop=stop_after_attempt(N_RUNS)))()

    assert result is None
    assert m.call_count == N_RUNS
    assert m.await_count == N_RUNS


async def test_retries_on_fn_that_eventually_succeeds():
    N_RUNS = 5
    call_results = [Exception] * (N_RUNS - 1) + [True]
    m = unittest.mock.AsyncMock(side_effect=call_results)

    result = await sit(m, retry=retry(stop=stop_after_attempt(N_RUNS)))()

    assert result
    assert m.call_count == N_RUNS
    assert m.await_count == N_RUNS


async def test_successful_fn_without_retries():
    m = unittest.mock.AsyncMock()

    await sit(m)()

    m.assert_called_once()
    m.assert_awaited()
