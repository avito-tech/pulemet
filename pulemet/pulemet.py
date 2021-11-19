import asyncio
import math
from typing import (
    Awaitable,
    Callable,
    Iterable,
    Optional,
    Sized,
    Tuple,
    Any,
)


async def as_completed_return_exception(coros: [Iterable[Awaitable], Sized]):
    """
    Wrapper for asyncio.as_completed. Equivalent return_exceptions=True from asyncio.gather.
    Returns `Exception` in case coroutine raises an exception.
    Args:
        coros: coroutines list.

    Returns:
        Results generator.

    """
    for elem in asyncio.as_completed(coros):
        try:
            res = await elem
        except Exception as err:
            res = err
        yield res


class Progress:
    """Progress bar mock."""

    def __init__(self, desc: str, total: int):
        self.desc = desc
        self.total = total

    def refresh(self):
        pass

    def close(self):
        pass

    def update(self):
        pass


class Monitor:
    def __init__(self, rps: float, tqdm: Any = None):
        self._rps = rps
        tqdm = tqdm or Progress

        self._pbar_total = tqdm(desc='Total', total=0)
        self._pbar_rps = tqdm(desc='Per second', total=0)
        self._pbar_retry = tqdm(desc='Retry', total=0)

    def __del__(self):
        for pbar in (self._pbar_total, self._pbar_rps, self._pbar_retry):
            pbar.refresh()
            pbar.close()

    def add(self, num: int):
        self._pbar_total.total += num
        self._pbar_total.refresh()

    def update(self, retry: bool = False):
        self._pbar_rps.update()
        if retry:
            self._pbar_retry.update()
        else:
            self._pbar_total.update()


class Pulemet:
    """Manage execution speed of coroutines."""

    def __init__(
        self,
        rps: float = 0.1,
        pool_size: Optional[int] = None,
        pbar: Any = None,
    ):
        """
        Gets config parameters.

        Args:
            rps: coroutines per second
            pool_size: working coroutines limit
            pbar: progress bar from tqdm. Example: from tqdm.auto import tqdm; Pulemet(pbar=tqdm())
        """
        self._rps_min, self._rps_max = 5, 10
        self._rps, self._burst = self._get_rps_and_burst(rps)

        if pool_size is not None and pool_size < 1:
            raise ValueError('Argument pool_size has to be greater 0')

        self._pool_size = pool_size
        if pool_size is None:
            self._pool_size = int(self._rps * 5) + 10  # 5 seconds accumulating, 10 - bias

        self._semaphore_time = asyncio.BoundedSemaphore(value=math.ceil(self._burst))
        self._semaphore_pool = asyncio.Semaphore(value=self._pool_size)

        self._timer_task = asyncio.ensure_future(self._timer())

        self._pbar = Monitor(rps=rps, tqdm=pbar)

    def __del__(self):
        self._timer_task.cancel()

    def process(self, coros: [Iterable[Awaitable], Sized]) -> [Iterable[Awaitable], Sized]:
        """
        Runs _wrap_coro for all coroutines in list.

        Args:
            coros: coroutines list

        Returns:
            New coroutines list

        """
        self._pbar.add(num=len(coros))
        res = [self._wrap_coro(coro) for coro in coros]

        return res

    def process_funcs(
        self,
        coro_func: Callable[..., Awaitable],
        coros_kwargs: [Iterable[dict], Sized],
        exceptions: Tuple[BaseException, ...],
        exceptions_max: Optional[int] = None,
    ) -> [Iterable[Awaitable], Sized]:
        """
        Runs _wrap_coro for all coroutines in list.

        Args:
            coro_func: async function
            coros_kwargs: list of kwargs for function
            exceptions: Exceptions object fot catching
            exceptions_max: Retry sort of thing, but with Exceptions

        Returns:
            New coroutines list

        """
        if hasattr(coros_kwargs, '__len__'):
            self._pbar.add(num=len(coros_kwargs))
        res = [
            self._warp_coro_func(
                coro_func=coro_func,
                exceptions=exceptions,
                exceptions_max=exceptions_max,
                **coro_kwargs,
            )
            for coro_kwargs in coros_kwargs
        ]

        return res

    def _get_rps_and_burst(self, rps: float):
        if rps <= self._rps_max:
            rps_target, burst = rps, 1
        else:
            burst_max = int(rps / self._rps_min)
            burst_min = math.ceil(rps / self._rps_max)
            res = []
            for burst in range(burst_min, burst_max + 1):
                rps_target = round(rps / burst, 2)
                prec = abs(rps - rps_target * burst) / rps * 100
                res.append((burst, rps_target, prec))
                if prec < 0.01:
                    break
            burst, rps_target, prec = sorted(res, key=lambda x: x[2])[0]

        return rps_target, burst

    async def _timer(self):
        """Освобождает семафор на исполнение корутины `burst` раз в `1 / rps` секунд."""
        while True:
            await asyncio.sleep(1 / self._rps)
            for ind in range(self._burst):
                try:
                    self._semaphore_time.release()
                except ValueError:
                    continue

    async def _wrap_coro(self, coro: Awaitable, update: bool = True) -> Awaitable:
        """
        Waiting for speed and pool size semaphores release then run coroutine.

        Args:
            coro: coroutine

        Returns:
            result of the original coroutine

        """
        async with self._semaphore_pool:
            await self._semaphore_time.acquire()
            if update:
                self._pbar.update(retry=False)
            result = await coro

        return result

    async def _warp_coro_func(
        self,
        coro_func: Callable[..., Awaitable],
        exceptions: Tuple[BaseException, ...],
        exceptions_max: Optional[int] = None,
        **coro_kwargs,
    ) -> Awaitable:
        cnt = 0
        while True:
            coro = coro_func(**coro_kwargs)
            try:
                coro = await self._wrap_coro(coro, update=False)
                self._pbar.update(retry=False)
                return coro
            except exceptions as exc:
                cnt += 1
                self._pbar.update(retry=True)
                if exceptions_max is not None and cnt == exceptions_max:
                    raise exc
                continue
