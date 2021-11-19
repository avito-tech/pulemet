import asyncio
from time import monotonic

from pulemet.pulemet import Pulemet


async def target(t: float = 0):
    await asyncio.sleep(t)
    return 1


async def sum_results(coros):
    s = 0
    for elem in asyncio.as_completed(coros):
        s += await elem

    return s


def run_with_timer(coro):
    start = monotonic()
    result = asyncio.get_event_loop().run_until_complete(coro)
    return result, monotonic() - start


def test_fast_coroutines():
    pulemet = Pulemet(rps=100)
    coroutines = pulemet.process([target() for _ in range(200)])

    result, time = run_with_timer(sum_results(coroutines))

    assert result == 200
    assert round(time, 1) == 2.0


def test_slow_coroutines():
    pulemet = Pulemet(rps=10)
    coroutines = pulemet.process([target(1) for _ in range(10)])

    result, time = run_with_timer(sum_results(coroutines))

    assert result == 10
    assert round(time, 1) == 1.9


def test_pool_size_limit():
    pulemet = Pulemet(rps=1, pool_size=1)
    coroutines = pulemet.process([target(1) for _ in range(10)])

    result, time = run_with_timer(sum_results(coroutines))

    assert result == 10
    assert round(time, 1) == 10.0


def test_process_funcs():
    pulemet = Pulemet(rps=1, pool_size=1)
    coroutines = pulemet.process_funcs(target, [{'t': 1}], ())

    result, time = run_with_timer(sum_results(coroutines))

    assert result == 1
    assert round(time, 1) == 1.0
