import random
import unittest.mock

import cachetools

from sitters import sit


async def test_caching_prevents_duplicate_runs():
    N_RUNS = 5
    EXPECTED_RESULT = random.random()
    CACHE = cachetools.LRUCache(maxsize=10)

    m = unittest.mock.AsyncMock(return_value=EXPECTED_RESULT)
    fn = sit(m, cache=CACHE)
    for _ in range(N_RUNS):
        result = await fn()
        assert result == EXPECTED_RESULT

    m.assert_called_once()
    m.assert_awaited_once()
    assert CACHE.currsize == 1


async def test_caching_with_different_runs():
    N_RUNS = 5
    CACHE = cachetools.LRUCache(maxsize=10)

    m = unittest.mock.AsyncMock()
    fn = sit(m, cache=CACHE)

    for i in range(N_RUNS):
        await fn(i)

    assert m.call_count == N_RUNS
    assert m.await_count == N_RUNS
    assert CACHE.currsize == N_RUNS


async def test_caching_with_some_different_runs_and_some_same_runs():
    EXPECTED_RUNS = 3
    CACHE = cachetools.LRUCache(maxsize=10)

    m = unittest.mock.AsyncMock()
    fn = sit(m, cache=CACHE)

    # run the function on a base set of inputs
    for i in range(EXPECTED_RUNS - 1):
        await fn(i)

    # run the function on a new set of inputs, some of which are repeated
    for i in range(EXPECTED_RUNS):
        await fn(i)

    assert m.call_count == EXPECTED_RUNS
    assert m.await_count == EXPECTED_RUNS
    assert CACHE.currsize == EXPECTED_RUNS


async def test_no_cache_removes_caching():
    EXPECTED_RUNS = 3

    m = unittest.mock.AsyncMock()
    fn = sit(m, cache=None)

    # run the function on a base set of inputs
    for _ in range(EXPECTED_RUNS):
        await fn()

    assert m.call_count == EXPECTED_RUNS
    assert m.await_count == EXPECTED_RUNS


async def test_cache_hit_returns_stored_value():
    CACHE = cachetools.LRUCache(maxsize=10)
    TARGET = random.random()

    m = unittest.mock.AsyncMock(return_value=TARGET)
    fn = sit(m, cache=CACHE)

    original_result = await fn()
    cached_result = await fn()

    assert original_result == TARGET
    assert cached_result == TARGET
    assert m.call_count == 1
    assert m.await_count == 1
    assert CACHE.currsize == 1
