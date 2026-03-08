# Background Task Manager — runs AI inference in a thread pool
# so Flask can respond to polling / health-check requests immediately.

import uuid
import time
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional
from concurrent.futures import ThreadPoolExecutor


@dataclass
class Task:
    task_id: str
    status: str = "pending"          # pending | processing | completed | failed
    progress: int = 0                # 0-100
    progress_message: str = ""
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)


class TaskManager:
    """In-memory background task manager backed by a ThreadPoolExecutor."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        # max_workers=1: YOLO models are NOT thread-safe (especially .track(persist=True)
        # which holds internal ByteTrack state). Concurrent inference on the same model
        # objects causes segfaults or corrupted results. Serialize all inference work.
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._tasks: Dict[str, Task] = {}
        self._lock = threading.Lock()

    # ---- public API ----

    def submit(self, fn: Callable, media_type: str = "image") -> str:
        """Submit *fn* for background execution. Returns a task_id."""
        task_id = uuid.uuid4().hex[:12]
        task = Task(task_id=task_id, status="pending", progress_message="Đang chờ xử lý...")

        with self._lock:
            self._tasks[task_id] = task

        def _wrapper():
            task.status = "processing"
            task.progress_message = "Đang xử lý..."
            try:
                result = fn(lambda pct, msg: self._update_progress(task_id, pct, msg))
                task.result = result
                task.status = "completed"
                task.progress = 100
                task.progress_message = "Hoàn tất!"
            except Exception as exc:
                task.status = "failed"
                task.error = str(exc)
                task.progress_message = "Lỗi xử lý"
                import traceback
                traceback.print_exc()

        self._executor.submit(_wrapper)
        # Garbage-collect old finished tasks
        self._cleanup_old_tasks()
        return task_id

    def get_task(self, task_id: str) -> Optional[Task]:
        with self._lock:
            return self._tasks.get(task_id)

    # ---- internals ----

    def _update_progress(self, task_id: str, pct: int, msg: str):
        task = self._tasks.get(task_id)
        if task:
            task.progress = pct
            task.progress_message = msg

    def _cleanup_old_tasks(self, max_age: float = 3600):
        """Remove completed/failed tasks older than *max_age* seconds."""
        now = time.time()
        with self._lock:
            stale = [
                tid for tid, t in self._tasks.items()
                if t.status in ("completed", "failed") and now - t.created_at > max_age
            ]
            for tid in stale:
                del self._tasks[tid]


# Singleton
task_manager = TaskManager()
