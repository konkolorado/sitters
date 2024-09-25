import functools
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

        self.result = anyio.Event()
        self.completed = anyio.Event()
        self.restarted = anyio.Event()

        self.send_stream, self.receive_stream = anyio.create_memory_object_stream(1)
        self.call_scope: anyio.CancelScope

    def _prepare_call(self):
        fn = functools.partial(self.sit.fn, *self.args, **self.kwargs)
        if self.sit.retry:
            fn = self.sit.retry(fn)

        return t.cast(t.Callable[[], t.Awaitable[R]], fn)

    async def start(self) -> R | None:
        with SitContext.for_sit(self.sit):
            async with anyio.create_task_group() as tg:
                tg.start_soon(self._watch_for_restarts, tg)
                tg.start_soon(self._watch_for_signals, tg)
                tg.start_soon(self._watch_for_result, tg)
                tg.start_soon(self._send_from_cache_or_run)

        return await self._get_result()

    async def _watch_for_result(self, tg: anyio.abc.TaskGroup):
        await self.result.wait()
        tg.cancel_scope.cancel()

    async def _get_result(self):
        return await self.receive_stream.receive()

    def _pause(self, tg: anyio.abc.TaskGroup):
        while True:
            signum = signal.sigwait(
                [
                    signal.SIGTERM,
                    signal.SIGINT,
                    signal.SIGKILL,
                    signal.SIGHUP,
                    signal.SIGUSR1,
                    signal.SIGUSR2,
                ]
            )
            match signum:
                case signal.SIGTERM | signal.SIGINT | signal.SIGKILL:
                    tg.cancel_scope.cancel()
                    break
                case signal.SIGHUP:
                    self.call_scope.cancel()
                    break
                case signal.SIGUSR1:
                    # this needs to be caught here, otherwise it will be
                    # processed if we are unpaused later
                    continue
                case signal.SIGUSR2:
                    # Interpret this as unpause
                    break

    async def _run_call(self) -> R | None:
        call = self._prepare_call()

        with anyio.CancelScope() as self.call_scope:
            with anyio.move_on_after(self.sit.timeout) as self.timeout_scope:
                await self._handle_startup()
                try:
                    result = await call()
                except anyio.get_cancelled_exc_class():
                    if self.timeout_scope.cancel_called:
                        with anyio.CancelScope(shield=True):
                            await self._handle_timeout()
                    elif self.call_scope.cancel_called:
                        with anyio.CancelScope(shield=True):
                            await self._handle_restarts()
                    else:
                        with anyio.CancelScope(shield=True):
                            await self._handle_cancellation()
                    raise
                except Exception:
                    with anyio.CancelScope(shield=True):
                        await self._handle_exception()
                    raise
                else:
                    with anyio.CancelScope(shield=True):
                        await self._handle_completion()
                    return result

    async def _watch_for_signals(self, tg: anyio.abc.TaskGroup):
        with anyio.open_signal_receiver(
            signal.SIGTERM, signal.SIGINT, signal.SIGHUP, signal.SIGUSR1, signal.SIGUSR2
        ) as signals:
            async for signum in signals:
                match signum:
                    case signal.SIGTERM | signal.SIGINT | signal.SIGKILL:
                        # CTRL-C or kill -15 received
                        tg.cancel_scope.cancel()
                    case signal.SIGHUP:
                        # kill -1 received
                        self.call_scope.cancel()
                    case signal.SIGUSR1:
                        # kill --SIGUSR1 received
                        self._pause(tg)
                    case signal.SIGUSR2:
                        # we need this to prevent a kill
                        pass

    async def _handle_startup(self):
        await self._run_hooks([get_this_sit().set_starting] + self.sit.startup_hooks)

    async def _handle_completion(self):
        await self._run_hooks(
            [get_this_sit().set_completed] + self.sit.completion_hooks
        )
        self.completed.set()

    async def _handle_exception(self):
        await self._run_hooks([get_this_sit().set_failed] + self.sit.exception_hooks)

    async def _handle_timeout(self):
        await self._run_hooks([get_this_sit().set_timedout] + self.sit.timeout_hooks)

    async def _handle_cancellation(self):
        await self._run_hooks(self.sit.cancellation_hooks)

    async def _watch_for_restarts(self, tg: anyio.abc.TaskGroup):
        await self.restarted.wait()
        self.restarted = anyio.Event()
        tg.start_soon(self._send_from_cache_or_run)
        tg.start_soon(self._watch_for_restarts, tg)

    async def _handle_restarts(self):
        await self._run_hooks(self.sit.restart_hooks)
        self.restarted.set()

    async def _run_hooks(self, hooks: list[Hooks], *args) -> None:
        if len(hooks) == 0:
            return

        async with create_task_group() as tg:
            [tg.start_soon(h, *args) for h in hooks]

    async def _send_from_cache_or_run(self):
        if self.sit.cache and self._cache_key in self.sit.cache:
            result = self.sit.cache.get(self._cache_key)
        else:
            try:
                result = await self._run_call()
            except anyio.get_cancelled_exc_class():
                # this task was cancelled, so use a None result
                result = None

        if self.sit.cache is not None and self.completed.is_set():
            # only cache the result if the task completed successfully
            self.sit.cache[self._cache_key] = t.cast(R, result)

        if self.restarted.is_set():
            # this task is being restarted, so don't send any results
            return

        with anyio.CancelScope(shield=True):
            await self.send_stream.send(result)
            self.result.set()

    @cached_property
    def _cache_key(self):
        return (
            (self.sit.fn.__name__,)
            + self.args
            + (self.KWD_MARK,)
            + tuple(sorted(self.kwargs.items()))
        )
