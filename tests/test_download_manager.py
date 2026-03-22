import threading
import time
import unittest

from src.download_manager import DownloadManager, DownloadTask, TaskStatus
from src.downloader import DownloadProgress, DownloadStatus


class FakeDownloader:
    def download(
        self,
        *,
        url,
        format_type,
        quality,
        progress_callback,
        playlist_title,
        cancel_event,
    ) -> bool:
        progress_callback(
            DownloadProgress(
                status=DownloadStatus.DOWNLOADING,
                title=url,
                progress=50.0,
                speed="1.0 MB/s",
                eta="0:01",
                filename="file.tmp",
            )
        )
        if cancel_event and cancel_event.is_set():
            progress_callback(
                DownloadProgress(
                    status=DownloadStatus.CANCELLED,
                    title=url,
                    progress=0.0,
                    speed="",
                    eta="",
                    filename="",
                    error="cancelled",
                )
            )
            return False
        progress_callback(
            DownloadProgress(
                status=DownloadStatus.COMPLETED,
                title=url,
                progress=100.0,
                speed="",
                eta="",
                filename="file.tmp",
            )
        )
        return True


class SlowDownloader:
    def download(
        self,
        *,
        url,
        format_type,
        quality,
        progress_callback,
        playlist_title,
        cancel_event,
    ) -> bool:
        for _ in range(10):
            if cancel_event and cancel_event.is_set():
                progress_callback(
                    DownloadProgress(
                        status=DownloadStatus.CANCELLED,
                        title=url,
                        progress=0.0,
                        speed="",
                        eta="",
                        filename="",
                        error="cancelled",
                    )
                )
                return False
            time.sleep(0.01)
        progress_callback(
            DownloadProgress(
                status=DownloadStatus.COMPLETED,
                title=url,
                progress=100.0,
                speed="",
                eta="",
                filename="file.tmp",
            )
        )
        return True


class DownloadManagerTests(unittest.TestCase):
    def test_executor_is_released_after_batch_completion(self) -> None:
        complete = threading.Event()
        manager = DownloadManager(
            downloader=FakeDownloader(),
            max_workers=2,
            on_batch_complete=complete.set,
        )

        manager.submit_tasks(
            [
                DownloadTask(task_id="a", url="a", title="A"),
                DownloadTask(task_id="b", url="b", title="B"),
            ]
        )

        self.assertTrue(complete.wait(timeout=2))
        self.assertFalse(manager.is_running())
        self.assertIsNone(manager._executor)
        self.assertEqual(manager.get_completed_ids(), {"a", "b"})

    def test_cancel_all_marks_tasks_cancelled_and_shuts_down_executor(self) -> None:
        manager = DownloadManager(
            downloader=SlowDownloader(),
            max_workers=2,
        )
        manager.submit_tasks(
            [
                DownloadTask(task_id="a", url="a", title="A"),
                DownloadTask(task_id="b", url="b", title="B"),
            ]
        )

        time.sleep(0.02)
        manager.cancel_all()

        self.assertFalse(manager.is_running())
        self.assertIsNone(manager._executor)
        statuses = {manager.get_task("a").status, manager.get_task("b").status}
        self.assertTrue(statuses.issubset({TaskStatus.CANCELLED, TaskStatus.COMPLETED}))


if __name__ == "__main__":
    unittest.main()
