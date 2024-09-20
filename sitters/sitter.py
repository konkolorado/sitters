import functools
import typing as t

from anyio import CancelScope, create_task_group, get_cancelled_exc_class, move_on_after

from .context import SitContext, get_this_sit

if t.TYPE_CHECKING:
    from .sit import Sit

Hooks = t.Callable[[], t.Awaitable[None]]
P = t.ParamSpec("P")
R = t.TypeVar("R")


class Sitter(t.Generic[P, R]):
    KWD_MARK = object()

    def __init__(self, sit: "Sit[P, R]", *args: P.args, **kwargs: P.kwargs) -> None:
        self.sit = sit
        self.args = args
        self.kwargs = kwargs

        self.timout_scope: CancelScope

    async def start(self) -> R | None:
        call = self._prepare_call()

        with SitContext.for_sitter(self.sit):
            with move_on_after(self.sit.timeout) as scope:
                self.timout_scope = scope
                return await call()

    def _prepare_call(self):
        fn = functools.partial(self.sit.fn, *self.args, **self.kwargs)
        if self.sit.retry:
            fn = self.sit.retry(fn)
        fn = functools.partial(self._with_hooks, fn)
        if self.sit.cache is not None:
            fn = functools.partial(self._with_caching, fn)
        return fn

    async def _with_hooks(self, call: t.Callable) -> R | None:
        await self._run_hooks(self._startup_hooks)

        try:
            result = await call()
        except* get_cancelled_exc_class():
            with CancelScope(shield=True):
                if self.timout_scope and self.timout_scope.cancel_called:
                    await self._run_hooks(self._timeout_hooks)
                else:
                    await self._run_hooks(self._interrupt_hooks)
        except* BaseException as excgrp:
            for exc in excgrp.exceptions:
                await self._run_hooks(self._exception_hooks)
        else:
            await self._run_hooks(self._completion_hooks)
            return result

    async def _run_hooks(self, hooks: list[Hooks], *args) -> None:
        if len(hooks) == 0:
            return

        async with create_task_group() as tg:
            [tg.start_soon(h, *args) for h in hooks]

    async def _with_caching(self, call: t.Callable) -> R:
        if self.sit.cache is None:
            return await call()

        key = self._generate_cache_key()
        if key in self.sit.cache:
            return t.cast(R, self.sit.cache.get(key))

        result = await call()
        self.sit.cache[key] = result
        return result

    def _generate_cache_key(self):
        return (
            (self.sit.fn.__name__,)
            + self.args
            + (self.KWD_MARK,)
            + tuple(sorted(self.kwargs.items()))
        )

    @property
    def _timeout_hooks(self) -> list[Hooks]:
        hooks: list[Hooks] = [get_this_sit().set_timedout]
        if self.sit.timeout_hooks:
            hooks.extend(self.sit.timeout_hooks)
        return hooks

    @property
    def _interrupt_hooks(self) -> list[Hooks]:
        return [get_this_sit().set_interrupted]

    @property
    def _completion_hooks(self) -> list[Hooks]:
        hooks: list[Hooks] = [get_this_sit().set_completed]
        if self.sit.completion_hooks:
            hooks.extend(self.sit.completion_hooks)
        return hooks

    @property
    def _startup_hooks(self) -> list[Hooks]:
        hooks: list[Hooks] = [get_this_sit().set_starting]
        if self.sit.startup_hooks:
            hooks.extend(self.sit.startup_hooks)
        return hooks

    @property
    def _exception_hooks(self) -> list[Hooks]:
        hooks: list[Hooks] = [get_this_sit().set_failed]
        if self.sit.exception_hooks:
            hooks.extend(self.sit.exception_hooks)
        return hooks
