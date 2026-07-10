"""Async helpers for blocking core operations."""

from __future__ import annotations

import asyncio
import atexit
from concurrent.futures import Future as ThreadFuture
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from threading import Lock
from typing import Any, Callable, TypeVar

T = TypeVar("T")

_EXECUTOR_LOCK = Lock()
_BLOCKING_EXECUTOR: ThreadPoolExecutor | None = None
_MAX_BLOCKING_WORKERS = 4


def _get_blocking_executor() -> ThreadPoolExecutor:
    global _BLOCKING_EXECUTOR
    with _EXECUTOR_LOCK:
        if _BLOCKING_EXECUTOR is None:
            _BLOCKING_EXECUTOR = ThreadPoolExecutor(
                max_workers=_MAX_BLOCKING_WORKERS,
                thread_name_prefix="devsynapse-blocking",
            )
        return _BLOCKING_EXECUTOR


async def run_blocking(func: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
    """Run blocking work without using asyncio's default executor.

    The dedicated executor keeps database and filesystem work out of asyncio's
    default executor. Some Python/runtime combinations fail to wake the event
    loop reliably for thread futures that complete from SQLite work, so this
    uses a small async polling interval instead of ``asyncio.wrap_future()``.
    """

    call = partial(func, *args, **kwargs)
    future: ThreadFuture[T] = _get_blocking_executor().submit(call)
    try:
        while not future.done():
            await asyncio.sleep(0.01)
        return future.result()
    except asyncio.CancelledError:
        future.cancel()
        raise


def shutdown_blocking_executor(*, wait: bool = False) -> None:
    """Stop the shared blocking executor."""

    global _BLOCKING_EXECUTOR
    with _EXECUTOR_LOCK:
        executor = _BLOCKING_EXECUTOR
        _BLOCKING_EXECUTOR = None
    if executor is not None:
        executor.shutdown(wait=wait, cancel_futures=True)


atexit.register(shutdown_blocking_executor)
