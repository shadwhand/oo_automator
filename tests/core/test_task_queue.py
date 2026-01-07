import pytest
import asyncio
from oo_automator.core.task_queue import TaskQueue


@pytest.mark.asyncio
async def test_task_queue_basic():
    queue = TaskQueue()

    await queue.put({"id": 1, "value": "a"})
    await queue.put({"id": 2, "value": "b"})

    assert queue.qsize() == 2

    task1 = await queue.get()
    assert task1["id"] == 1

    task2 = await queue.get()
    assert task2["id"] == 2


@pytest.mark.asyncio
async def test_task_queue_priority():
    queue = TaskQueue()

    await queue.put({"id": 1}, priority=2)
    await queue.put({"id": 2}, priority=1)  # Higher priority
    await queue.put({"id": 3}, priority=3)

    task = await queue.get()
    assert task["id"] == 2  # Should get highest priority first


@pytest.mark.asyncio
async def test_task_queue_requeue():
    queue = TaskQueue()

    await queue.put({"id": 1, "attempts": 0})
    task = await queue.get()

    task["attempts"] += 1
    await queue.requeue(task)

    requeued = await queue.get()
    assert requeued["attempts"] == 1


def test_task_queue_stats():
    queue = TaskQueue()
    stats = queue.get_stats()

    assert "pending" in stats
    assert "completed" in stats
    assert "failed" in stats
