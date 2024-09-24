import functools
import os
import signal
import typing as t
from functools import cached_property

import anyio
import anyio.abc
from anyio import create_task_group

from .context import SitContext, get_this_sit

if t.TYPE_CHECKING:
    from .sit import Sit


Hooks = t.Callable[[], t.Awaitable[None]]
P = t.ParamSpec("P")
R = t.TypeVar("R")


class Sitter(t.Generic[P, R]):
    KWD_MARK = object()

    def __init__(self, sit: "Sit[P, R]", *args: P.args, **kwargs: P.kwargs):
        self.sit = sit
        self.args = args
        self.kwargs = kwargs

        self.started = anyio.Event()
        self.completed = anyio.Event()
        self.failed = anyio.Event()
        self.timedout = anyio.Event()
        self.cancelled = anyio.Event()
        self.restarted = anyio.Event()

        self.send_stream, self.receive_stream = anyio.create_memory_object_stream(1)
        self.call_scope: anyio.CancelScope
        self.timeout_scope: anyio.CancelScope

    def _prepare_call(self):
        fn = functools.partial(self.sit.fn, *self.args, **self.kwargs)
        if self.sit.retry:
            fn = self.sit.retry(fn)

        return t.cast(t.Callable[[], t.Awaitable[R]], fn)

    async def start(self) -> R | None:
        with SitContext.for_sit(self.sit):
            async with anyio.create_task_group() as tg:
                tg.start_soon(self._watch_for_started)
                tg.start_soon(self._watch_for_completion, tg)
                tg.start_soon(self._watch_for_exception, tg)
                tg.start_soon(self._watch_for_timeout, tg)
                tg.start_soon(self._watch_for_restarts, tg)
                tg.start_soon(self._watch_for_cancellation, tg)
                tg.start_soon(self._watch_for_signals, tg)
                tg.start_soon(self._send_from_cache_or_run)

        if self.completed.is_set():
            return await self._get_result()
        return None

    async def _get_result(self):
        return await self.receive_stream.receive()

    async def _run_call(self) -> R | None:
        call = self._prepare_call()

        with anyio.CancelScope() as self.call_scope:
            with anyio.move_on_after(self.sit.timeout) as self.timeout_scope:
                self.started.set()
                await anyio.sleep(0.05)  # give hooks a chance to run
                try:
                    print("This is my PID", os.getpid())
                    result = await call()
                except anyio.get_cancelled_exc_class():
                    if self.timeout_scope.cancel_called:
                        print("set timeout")
                        self.timedout.set()
                    # elif self.restarted.is_set():
                    #    print("something restarted us")
                    elif self.call_scope.cancel_called:
                        print("something restarted us")
                        self.restarted.set()
                    else:
                        print("something upstairs cancelled us")
                        # self.cancelled.set()
                    # print(f"{self.call_scope.cancel_called=}")
                    raise
                except Exception:
                    self.failed.set()
                    raise
                else:
                    self.completed.set()
                    return result

    async def _watch_for_signals(self, tg: anyio.abc.TaskGroup):
        with anyio.open_signal_receiver(
            signal.SIGTERM, signal.SIGHUP, signal.SIGINT
        ) as signals:
            async for signum in signals:
                match signum:
                    case signal.SIGTERM | signal.SIGINT | signal.SIGKILL:
                        print("kill 15 / CTRL-C recvd")
                        # CTRL-C or kill -15 received
                        # tg.cancel_scope.cancel()
                        self.cancelled.set()
                    case signal.SIGHUP:
                        print("kill -1 recvd")
                        # kill -1 received
                        # self.restarted.set()
                        self.call_scope.cancel()
                        # self.call_scope = anyio.CancelScope()
                        tg.start_soon(self._send_from_cache_or_run)
                    case signal.SIGUSR1:
                        # pause the sit???
                        ...
                    case signal.SIGUSR2:
                        # resume the sit???
                        ...

    async def _watch_for_started(self):
        await self.started.wait()
        await self._run_hooks([get_this_sit().set_starting] + self.sit.startup_hooks)

    async def _watch_for_completion(self, tg: anyio.abc.TaskGroup):
        await self.completed.wait()
        await self._run_hooks(
            [get_this_sit().set_completed] + self.sit.completion_hooks
        )
        tg.cancel_scope.cancel()

    async def _watch_for_exception(self, tg: anyio.abc.TaskGroup):
        await self.failed.wait()
        await self._run_hooks([get_this_sit().set_failed] + self.sit.exception_hooks)
        tg.cancel_scope.cancel()

    async def _watch_for_timeout(self, tg: anyio.abc.TaskGroup):
        await self.timedout.wait()
        await self._run_hooks([get_this_sit().set_timedout] + self.sit.timeout_hooks)
        tg.cancel_scope.cancel()

    async def _watch_for_restarts(self, tg: anyio.abc.TaskGroup):
        await self.restarted.wait()
        await self._run_hooks(self.sit.restart_hooks)
        # tg.cancel_scope.cancel()

        # self.call_scope.cancel()
        # self.call_scope = anyio.CancelScope()
        self.restarted = anyio.Event()
        # tg.start_soon(self._send_from_cache_or_run)

    async def _watch_for_cancellation(self, tg: anyio.abc.TaskGroup):
        await self.cancelled.wait()
        await self._run_hooks(self.sit.cancellation_hooks)
        tg.cancel_scope.cancel()

    async def _run_hooks(self, hooks: list[Hooks], *args) -> None:
        if len(hooks) == 0:
            return

        async with create_task_group() as tg:
            [tg.start_soon(h, *args) for h in hooks]

    async def _send_from_cache_or_run(self):
        from_cache = False

        if self.sit.cache and self._cache_key in self.sit.cache:
            result = self.sit.cache.get(self._cache_key)
            from_cache = True
        else:
            result = await self._run_call()

        if (
            self.sit.cache is not None
            and not self.timedout.is_set()
            and not self.failed.is_set()
            and not self.cancelled.is_set()
            and not self.restarted.is_set()
        ):
            self.sit.cache[self._cache_key] = t.cast(R, result)

        # only send a result if a terminal event happened
        if (
            from_cache
            or self.completed.is_set()
            or self.timedout.is_set()
            or self.failed.is_set()
        ):
            self.completed.set()
            await self.send_stream.send(result)

    @cached_property
    def _cache_key(self):
        return (
            (self.sit.fn.__name__,)
            + self.args
            + (self.KWD_MARK,)
            + tuple(sorted(self.kwargs.items()))
        )
