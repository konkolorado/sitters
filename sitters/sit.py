import functools
import typing as t

from cachetools import Cache

from .sitter import Sitter

P = t.ParamSpec("P")
R = t.TypeVar("R")


Hooks = t.Callable[[], t.Awaitable[None]]


class Sit(t.Generic[P, R]):
    def __init__(
        self,
        fn: t.Callable[P, R],
        *,
        startup_hooks: list[Hooks] | None = None,
        completion_hooks: list[Hooks] | None = None,
        exception_hooks: list[Hooks] | None = None,
        timeout_hooks: list[Hooks] | None = None,
        cancellation_hooks: list[Hooks] | None = None,
        restart_hooks: list[Hooks] | None = None,
        retry: t.Callable[[t.Callable], t.Callable] | None = None,
        cache: Cache[t.Any, R] | None = None,
        timeout: int | None = None,
    ) -> None:
        functools.update_wrapper(self, fn)
        self.fn = fn
        self.retry = retry
        self.cache = cache
        self.timeout = timeout
        self.startup_hooks = startup_hooks or []
        self.completion_hooks = completion_hooks or []
        self.exception_hooks = exception_hooks or []
        self.timeout_hooks = timeout_hooks or []
        self.cancellation_hooks = cancellation_hooks or []
        self.restart_hooks = restart_hooks or []

    async def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R | None:
        return await Sitter(self, *args, **kwargs).start()


@t.overload
def sit(
    fn: t.Callable[P, R],
    *,
    startup_hooks: list[Hooks] | None = None,
    completion_hooks: list[Hooks] | None = None,
    exception_hooks: list[Hooks] | None = None,
    timeout_hooks: list[Hooks] | None = None,
    cancellation_hooks: list[Hooks] | None = None,
    restart_hooks: list[Hooks] | None = None,
    retry: t.Callable[[t.Callable], t.Callable] | None = None,
    cache: Cache | None = None,
    timeout: int | None = None,
) -> Sit[P, R]:
    ...


@t.overload
def sit(
    *,
    startup_hooks: list[Hooks] | None = None,
    completion_hooks: list[Hooks] | None = None,
    exception_hooks: list[Hooks] | None = None,
    timeout_hooks: list[Hooks] | None = None,
    cancellation_hooks: list[Hooks] | None = None,
    restart_hooks: list[Hooks] | None = None,
    retry: t.Callable[[t.Callable], t.Callable] | None = None,
    cache: Cache | None = None,
    timeout: int | None = None,
) -> t.Callable[[t.Callable[P, R]], Sit[P, R]]:
    ...


def sit(
    fn: t.Callable[P, R] | None = None,
    startup_hooks: list[Hooks] | None = None,
    completion_hooks: list[Hooks] | None = None,
    exception_hooks: list[Hooks] | None = None,
    timeout_hooks: list[Hooks] | None = None,
    cancellation_hooks: list[Hooks] | None = None,
    restart_hooks: list[Hooks] | None = None,
    retry: t.Callable[[t.Callable], t.Callable] | None = None,
    cache: Cache | None = None,
    timeout: int | None = None,
) -> Sit[P, R] | t.Callable[[t.Callable[P, R]], Sit[P, R]]:
    if fn:
        return t.cast(
            Sit[P, R],
            Sit(
                fn,
                startup_hooks=startup_hooks,
                completion_hooks=completion_hooks,
                exception_hooks=exception_hooks,
                timeout_hooks=timeout_hooks,
                cancellation_hooks=cancellation_hooks,
                restart_hooks=restart_hooks,
                retry=retry,
                cache=cache,
                timeout=timeout,
            ),
        )
    else:
        return t.cast(
            t.Callable[[t.Callable[P, R]], Sit[P, R]],
            functools.partial(
                sit,
                startup_hooks=startup_hooks,
                completion_hooks=completion_hooks,
                exception_hooks=exception_hooks,
                timeout_hooks=timeout_hooks,
                cancellation_hooks=cancellation_hooks,
                restart_hooks=restart_hooks,
                retry=retry,
                cache=cache,
                timeout=timeout,
            ),
        )
