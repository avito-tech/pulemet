=======
Pulemet
=======

Execute coroutines with limitations. Take a look at following examples. 

Uniform and steady execution
============================

Let's imagine we have some service. We want to get something like 10k results from that server.
While we don't want to cost trouble target server we can use Pulemet with `rps` parameter.
It will run just `rps` requests per second. And we won't damage server. 
Also, we may need to use `pool_size` parameter if server doesn't answer fast enough.
That parameter will prevent creating new connections above the limit if current still working.

.. code-block:: python

 import asyncio

    from pulemet.pulemet import Pulemet


    async def http_request(t: float = 0):
        """Let's say we go somewhere by http here."""
        await asyncio.sleep(t)
        return 1


    async def sum_results(coros):
        s = 0
        for elem in asyncio.as_completed(coros):
            s += await elem

        return s


    pulemet = Pulemet(rps=1, pool_size=20)
    coroutines = pulemet.process([http_request() for _ in range(10)])

    result = asyncio.get_event_loop().run_until_complete(sum_results(coroutines))

Functions and retries
=====================

You can run some async function with list of arguments and catch certain exceptions and even try call it again(few times).
All of these in following example.

.. code-block:: python

    import asyncio

    from pulemet.pulemet import Pulemet


    async def func(ind):
        await asyncio.sleep(0.001)
        if ind % 2 == 0:
            raise ValueError
        return ind


    def main():
        pulemet = Pulemet(rps=10)

        coros_pulemet = pulemet.process_funcs(
            coro_func=func,
            coros_kwargs=({'ind': i} for i in range(0, 20)),
            exceptions=(ValueError,),
            exceptions_max=5,
        )
        coroutines = asyncio.gather(*coros_pulemet, return_exceptions=True)

        asyncio.get_event_loop().run_until_complete(coroutines)


    if __name__ == '__main__':
    main()


Progress Bar Integration
========================

That example explain how you can see execution progress this tqdm.

.. code-block:: python

    import asyncio

    from tqdm.auto import tqdm

    from pulemet.pulemet import Pulemet


    async def target(t: float = 0):
        await asyncio.sleep(t)
        return 1


    async def sum_results(coros):
        s = 0
        for elem in asyncio.as_completed(coros):
            s += await elem

        return s


    pulemet = Pulemet(rps=1, pbar=tqdm)
    coroutines = pulemet.process([target() for _ in range(10)])

    result = asyncio.get_event_loop().run_until_complete(sum_results(coroutines))

You will see something like that.

.. code-block:: sh

    Total: 0it [00:00, ?it/s]
    Per second: 0it [00:00, ?it/s]

    Total:   0%|          | 0/10 [00:00<?, ?it/s]
    Total:  20%|██        | 2/10 [00:01<00:04,  1.99it/s]
    Total:  30%|███       | 3/10 [00:02<00:04,  1.40it/s]
    Total:  40%|████      | 4/10 [00:03<00:04,  1.22it/s]
    Total:  50%|█████     | 5/10 [00:04<00:04,  1.13it/s]
    Total:  60%|██████    | 6/10 [00:05<00:03,  1.08it/s]
    Total:  70%|███████   | 7/10 [00:06<00:02,  1.05it/s]
    Total:  80%|████████  | 8/10 [00:07<00:01,  1.04it/s]
    Total:  90%|█████████ | 9/10 [00:08<00:00,  1.02it/s]
    Total: 100%|██████████| 10/10 [00:09<00:00,  1.02it/s]

