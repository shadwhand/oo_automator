"""Async task queue for managing backtest tasks."""
import asyncio
from dataclasses import dataclass, field
from typing import Any, Optional
import heapq


@dataclass(order=True)
class PrioritizedTask:
    """Task wrapper with priority for heap queue."""
    priority: int
    sequence: int
    task: Any = field(compare=False)


class TaskQueue:
    """Async priority queue for backtest tasks."""

    def __init__(self, max_retries: int = 3):
        self._heap: list[PrioritizedTask] = []
        self._lock = asyncio.Lock()
        self._not_empty = asyncio.Condition(self._lock)
        self._sequence = 0
        self.max_retries = max_retries

        self._completed = 0
        self._failed = 0

    async def put(self, task: dict, priority: int = 5) -> None:
        """Add a task to the queue."""
        async with self._lock:
            self._sequence += 1
            heapq.heappush(
                self._heap,
                PrioritizedTask(priority, self._sequence, task)
            )
            self._not_empty.notify()

    async def get(self, timeout: Optional[float] = None) -> dict:
        """Get the highest priority task."""
        async with self._not_empty:
            while not self._heap:
                try:
                    await asyncio.wait_for(
                        self._not_empty.wait(),
                        timeout=timeout
                    )
                except asyncio.TimeoutError:
                    raise asyncio.QueueEmpty()

            item = heapq.heappop(self._heap)
            return item.task

    async def requeue(self, task: dict, priority: int = 10) -> None:
        """Requeue a failed task with lower priority."""
        attempts = task.get("attempts", 0)
        if attempts < self.max_retries:
            await self.put(task, priority=priority)
        else:
            self._failed += 1

    def qsize(self) -> int:
        """Return number of pending tasks."""
        return len(self._heap)

    def empty(self) -> bool:
        """Return True if queue is empty."""
        return len(self._heap) == 0

    def mark_completed(self) -> None:
        """Mark a task as completed."""
        self._completed += 1

    def mark_failed(self) -> None:
        """Mark a task as permanently failed."""
        self._failed += 1

    def get_stats(self) -> dict:
        """Get queue statistics."""
        return {
            "pending": len(self._heap),
            "completed": self._completed,
            "failed": self._failed,
        }

    async def clear(self) -> None:
        """Clear all pending tasks."""
        async with self._lock:
            self._heap.clear()
