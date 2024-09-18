import datetime
import typing as t
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field

from .states import SitState

if t.TYPE_CHECKING:
    from .sitter import Sitter


__var__: ContextVar["SitContext"] = ContextVar("SitContext")


def _get_tz_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def get_this_sit() -> "SitContext":
    try:
        return SitContext.get()
    except LookupError:
        raise RuntimeError("Sit context is only available from within a sit")


@dataclass
class SitContext:
    sitter: "Sitter"
    name: str
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    started_at: datetime.datetime = field(default_factory=_get_tz_now)
    stopped_at: datetime.datetime | None = None
    state: SitState = SitState.PENDING

    @classmethod
    def for_sitter(cls, sitter: "Sitter") -> "SitContext":
        return cls(sitter=sitter, name=sitter.fn.__name__)

    @classmethod
    def get(cls) -> "SitContext":
        return __var__.get()

    def __enter__(self):
        self._token = __var__.set(self)
        return self

    def __exit__(self, *_):
        __var__.reset(self._token)

    async def set_completed(self):
        self.state = SitState.COMPLETED
        self.stopped_at = _get_tz_now()

    async def set_timedout(self):
        self.state = SitState.CANCELLED
        self.stopped_at = _get_tz_now()

    async def set_starting(self):
        self.state = SitState.RUNNING

    async def set_failed(self):
        self.state = SitState.FAILED
        self.stopped_at = _get_tz_now()
