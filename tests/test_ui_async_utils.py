import threading
import time
import unittest
from typing import Callable

from src.ui.async_utils import BackgroundTaskPool, DebouncedCallback


class FakeScheduler:
    def __init__(self) -> None:
        self._callbacks: dict[int, Callable[[], None]] = {}
        self._next_handle = 0

    def schedule(self, _delay_ms: int, callback) -> int:
        handle = self._next_handle
        self._next_handle += 1
        self._callbacks[handle] = callback
        return handle

    def cancel(self, handle: int) -> None:
        self._callbacks.pop(handle, None)

    def run_pending(self) -> None:
        callbacks = list(self._callbacks.values())
        self._callbacks.clear()
        for callback in callbacks:
            callback()


class UiAsyncUtilsTests(unittest.TestCase):
    def test_debounced_callback_only_runs_latest_token(self) -> None:
        scheduler = FakeScheduler()
        debouncer = DebouncedCallback(scheduler.schedule, scheduler.cancel, delay_ms=50)
        seen: list[tuple[str, int]] = []

        first_token = debouncer.schedule(lambda token: seen.append(("first", token)))
        second_token = debouncer.schedule(lambda token: seen.append(("second", token)))
        scheduler.run_pending()

        self.assertEqual(first_token, 1)
        self.assertEqual(second_token, 2)
        self.assertEqual(seen, [("second", 2)])

        flushed_token = debouncer.flush(lambda token: seen.append(("flush", token)))
        self.assertEqual(flushed_token, 3)
        self.assertEqual(seen[-1], ("flush", 3))

    def test_background_task_pool_limits_concurrency(self) -> None:
        pool = BackgroundTaskPool(2)
        active = 0
        max_active = 0
        lock = threading.Lock()

        def worker() -> int:
            nonlocal active, max_active
            with lock:
                active += 1
                max_active = max(max_active, active)
            time.sleep(0.05)
            with lock:
                active -= 1
            return 1

        futures = [pool.submit(worker) for _ in range(6)]
        results = [future.result(timeout=1) for future in futures]
        pool.shutdown()

        self.assertEqual(sum(results), 6)
        self.assertLessEqual(max_active, 2)


if __name__ == "__main__":
    unittest.main()
