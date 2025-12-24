"""
Download manager for SandSound.
Handles concurrent downloads using a thread pool.
"""

import threading
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set
from enum import Enum

from .downloader import Downloader, DownloadProgress, DownloadStatus


class TaskStatus(Enum):
    """Status of a download task in the queue."""
    QUEUED = "queued"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class DownloadTask:
    """Represents a single download task."""
    task_id: str
    url: str
    title: str
    format_type: str = "mp3"
    quality: str = "best"
    status: TaskStatus = TaskStatus.QUEUED
    progress: float = 0.0
    speed: str = ""
    eta: str = ""
    error: Optional[str] = None


@dataclass
class AggregateProgress:
    """Aggregated progress for all active downloads."""
    total_tasks: int
    completed_tasks: int
    active_tasks: int
    queued_tasks: int
    failed_tasks: int
    overall_progress: float  # 0.0 to 100.0
    total_speed: str
    active_titles: List[str] = field(default_factory=list)


class DownloadManager:
    """
    Manages concurrent downloads using a thread pool.
    
    Supports downloading multiple files simultaneously with
    aggregated progress tracking and per-task callbacks.
    """
    
    DEFAULT_MAX_WORKERS = 4
    
    def __init__(
        self,
        downloader: Downloader,
        max_workers: int = DEFAULT_MAX_WORKERS,
        on_task_update: Optional[Callable[[DownloadTask], None]] = None,
        on_aggregate_update: Optional[Callable[[AggregateProgress], None]] = None,
        on_batch_complete: Optional[Callable[[], None]] = None,
    ) -> None:
        """
        Initialize download manager.
        
        Args:
            downloader: Base downloader instance for configuration
            max_workers: Maximum concurrent downloads (1-8)
            on_task_update: Callback for individual task progress
            on_aggregate_update: Callback for overall progress
            on_batch_complete: Callback when all tasks complete
        """
        self._base_downloader = downloader
        self._max_workers = min(max(1, max_workers), 8)
        self._on_task_update = on_task_update
        self._on_aggregate_update = on_aggregate_update
        self._on_batch_complete = on_batch_complete
        
        self._executor: Optional[ThreadPoolExecutor] = None
        self._tasks: Dict[str, DownloadTask] = {}
        self._futures: Dict[str, Future] = {}
        self._lock = threading.Lock()
        self._cancel_flags: Dict[str, threading.Event] = {}
        self._is_running = False
    
    def submit_tasks(self, tasks: List[DownloadTask]) -> None:
        """
        Submit a batch of download tasks.
        
        Args:
            tasks: List of download tasks to queue
        """
        with self._lock:
            self._is_running = True
            self._executor = ThreadPoolExecutor(max_workers=self._max_workers)
            
            for task in tasks:
                self._tasks[task.task_id] = task
                self._cancel_flags[task.task_id] = threading.Event()
                
                future = self._executor.submit(
                    self._download_task,
                    task
                )
                self._futures[task.task_id] = future
                future.add_done_callback(
                    lambda f, tid=task.task_id: self._on_task_done(tid)
                )
    
    def _download_task(self, task: DownloadTask) -> bool:
        """
        Execute a single download task.
        
        Args:
            task: The task to download
            
        Returns:
            True if download succeeded
        """
        # Update status to active
        with self._lock:
            task.status = TaskStatus.ACTIVE
        self._notify_task_update(task)
        self._notify_aggregate_update()
        
        # Create progress callback for this task
        def progress_callback(progress: DownloadProgress) -> None:
            # Check for cancellation
            if self._cancel_flags.get(task.task_id, threading.Event()).is_set():
                raise Exception("Download cancelled")
            
            with self._lock:
                task.progress = progress.progress
                task.speed = progress.speed
                task.eta = progress.eta
                
                if progress.status == DownloadStatus.COMPLETED:
                    task.status = TaskStatus.COMPLETED
                    task.progress = 100.0
                elif progress.status == DownloadStatus.FAILED:
                    task.status = TaskStatus.FAILED
                    task.error = progress.error
            
            self._notify_task_update(task)
            self._notify_aggregate_update()
        
        try:
            success = self._base_downloader.download(
                url=task.url,
                format_type=task.format_type,
                quality=task.quality,
                progress_callback=progress_callback,
            )
            
            with self._lock:
                if success:
                    task.status = TaskStatus.COMPLETED
                    task.progress = 100.0
                else:
                    task.status = TaskStatus.FAILED
                    
            return success
            
        except Exception as e:
            with self._lock:
                if self._cancel_flags.get(task.task_id, threading.Event()).is_set():
                    task.status = TaskStatus.CANCELLED
                else:
                    task.status = TaskStatus.FAILED
                    task.error = str(e)
            return False
    
    def _on_task_done(self, task_id: str) -> None:
        """Handle task completion callback."""
        self._notify_task_update(self._tasks.get(task_id))
        self._notify_aggregate_update()
        
        # Check if all tasks are done
        with self._lock:
            all_done = all(
                t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)
                for t in self._tasks.values()
            )
        
        if all_done:
            self._is_running = False
            if self._on_batch_complete:
                self._on_batch_complete()
    
    def _notify_task_update(self, task: Optional[DownloadTask]) -> None:
        """Send task update to callback."""
        if task and self._on_task_update:
            self._on_task_update(task)
    
    def _notify_aggregate_update(self) -> None:
        """Calculate and send aggregate progress update."""
        if not self._on_aggregate_update:
            return
        
        with self._lock:
            tasks = list(self._tasks.values())
        
        if not tasks:
            return
        
        completed = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)
        active = sum(1 for t in tasks if t.status == TaskStatus.ACTIVE)
        queued = sum(1 for t in tasks if t.status == TaskStatus.QUEUED)
        failed = sum(1 for t in tasks if t.status in (TaskStatus.FAILED, TaskStatus.CANCELLED))
        
        # Calculate overall progress
        total_progress = 0.0
        for t in tasks:
            if t.status == TaskStatus.COMPLETED:
                total_progress += 100.0
            elif t.status == TaskStatus.ACTIVE:
                total_progress += t.progress
        
        overall = total_progress / len(tasks) if tasks else 0.0
        
        # Sum speeds from active downloads
        total_speed = self._sum_speeds(tasks)
        
        # Get active titles
        active_titles = [t.title for t in tasks if t.status == TaskStatus.ACTIVE]
        
        aggregate = AggregateProgress(
            total_tasks=len(tasks),
            completed_tasks=completed,
            active_tasks=active,
            queued_tasks=queued,
            failed_tasks=failed,
            overall_progress=overall,
            total_speed=total_speed,
            active_titles=active_titles,
        )
        
        self._on_aggregate_update(aggregate)
    
    def _sum_speeds(self, tasks: List[DownloadTask]) -> str:
        """Sum speeds from all active tasks."""
        total_bytes = 0.0
        
        for t in tasks:
            if t.status != TaskStatus.ACTIVE or not t.speed:
                continue
            
            # Parse speed string back to bytes/s
            speed = t.speed.strip()
            if speed.endswith("MB/s"):
                total_bytes += float(speed[:-4].strip()) * 1024 * 1024
            elif speed.endswith("KB/s"):
                total_bytes += float(speed[:-4].strip()) * 1024
            elif speed.endswith("B/s"):
                total_bytes += float(speed[:-3].strip())
        
        # Format back to string
        if total_bytes > 1024 * 1024:
            return f"{total_bytes / (1024 * 1024):.1f} MB/s"
        elif total_bytes > 1024:
            return f"{total_bytes / 1024:.1f} KB/s"
        elif total_bytes > 0:
            return f"{total_bytes:.0f} B/s"
        return ""
    
    def cancel_all(self) -> None:
        """Cancel all pending and active downloads."""
        with self._lock:
            # Set cancel flags
            for flag in self._cancel_flags.values():
                flag.set()
            
            # Update task statuses
            for task in self._tasks.values():
                if task.status in (TaskStatus.QUEUED, TaskStatus.ACTIVE):
                    task.status = TaskStatus.CANCELLED
        
        # Shutdown executor
        if self._executor:
            self._executor.shutdown(wait=False)
            self._executor = None
        
        self._is_running = False
    
    def cancel_task(self, task_id: str) -> None:
        """Cancel a specific task."""
        with self._lock:
            if task_id in self._cancel_flags:
                self._cancel_flags[task_id].set()
            
            if task_id in self._tasks:
                task = self._tasks[task_id]
                if task.status in (TaskStatus.QUEUED, TaskStatus.ACTIVE):
                    task.status = TaskStatus.CANCELLED
    
    def is_running(self) -> bool:
        """Check if downloads are in progress."""
        return self._is_running
    
    def get_task(self, task_id: str) -> Optional[DownloadTask]:
        """Get a task by ID."""
        return self._tasks.get(task_id)
    
    def get_completed_ids(self) -> Set[str]:
        """Get set of completed task IDs."""
        with self._lock:
            return {
                tid for tid, t in self._tasks.items()
                if t.status == TaskStatus.COMPLETED
            }
    
    def clear(self) -> None:
        """Clear all tasks and reset state."""
        self.cancel_all()
        with self._lock:
            self._tasks.clear()
            self._futures.clear()
            self._cancel_flags.clear()
