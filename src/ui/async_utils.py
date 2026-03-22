"""
Reusable async helpers for UI components.
"""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from typing import Callable, Optional


class DebouncedCallback:
    """Schedule callbacks so only the latest pending invocation runs."""

    def __init__(
        self,
        schedule: Callable[[int, Callable[[], None]], object],
        cancel: Callable[[object], None],
        delay_ms: int = 350,
    ) -> None:
        self._schedule = schedule
        self._cancel = cancel
        self._delay_ms = delay_ms
        self._handle: Optional[object] = None
        self._token = 0

    @property
    def current_token(self) -> int:
        """Return the latest issued token."""
        return self._token

    def schedule(self, callback: Callable[[int], None]) -> int:
        """Schedule a callback and cancel the previously pending one."""
        self.cancel_pending()
        self._token += 1
        token = self._token

        def runner() -> None:
            self._handle = None
            callback(token)

        self._handle = self._schedule(self._delay_ms, runner)
        return token

    def flush(self, callback: Callable[[int], None]) -> int:
        """Run a callback immediately with a fresh token."""
        self.cancel_pending()
        self._token += 1
        token = self._token
        callback(token)
        return token

    def cancel_pending(self) -> None:
        """Cancel the currently pending callback, if any."""
        if self._handle is None:
            return
        self._cancel(self._handle)
        self._handle = None


class BackgroundTaskPool:
    """Small wrapper around ThreadPoolExecutor with a fixed worker cap."""

    def __init__(self, max_workers: int) -> None:
        self.max_workers = max(1, max_workers)
        self._executor = ThreadPoolExecutor(max_workers=self.max_workers)

    def submit(self, func: Callable, *args, **kwargs) -> Future:
        """Submit a task to the underlying pool."""
        return self._executor.submit(func, *args, **kwargs)

    def shutdown(
        self,
        *,
        wait: bool = False,
        cancel_futures: bool = True,
    ) -> None:
        """Stop the executor without waiting for queued work."""
        self._executor.shutdown(wait=wait, cancel_futures=cancel_futures)
