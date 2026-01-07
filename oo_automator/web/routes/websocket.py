"""WebSocket routes for real-time updates."""
import asyncio
from typing import Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlmodel import select

from ...db.connection import get_engine, get_session
from ...db.models import Run, Task

router = APIRouter()


class ConnectionManager:
    """Manage WebSocket connections for a specific run."""

    def __init__(self):
        self.active_connections: dict[int, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, run_id: int):
        """Accept connection and register for run updates."""
        await websocket.accept()
        if run_id not in self.active_connections:
            self.active_connections[run_id] = set()
        self.active_connections[run_id].add(websocket)

    def disconnect(self, websocket: WebSocket, run_id: int):
        """Remove connection from run updates."""
        if run_id in self.active_connections:
            self.active_connections[run_id].discard(websocket)
            if not self.active_connections[run_id]:
                del self.active_connections[run_id]

    async def broadcast(self, run_id: int, message: dict):
        """Send message to all connections watching a run."""
        if run_id in self.active_connections:
            dead_connections = []
            for connection in self.active_connections[run_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    dead_connections.append(connection)

            for conn in dead_connections:
                self.active_connections[run_id].discard(conn)


manager = ConnectionManager()


async def get_run_status(run_id: int) -> dict:
    """Get current run status with progress."""
    engine = get_engine()
    session = get_session(engine)

    try:
        # Get run
        run_stmt = select(Run).where(Run.id == run_id)
        run = session.exec(run_stmt).first()
        if not run:
            return {"error": "Run not found"}

        # Get task counts
        tasks_stmt = select(Task).where(Task.run_id == run_id)
        tasks = list(session.exec(tasks_stmt).all())

        total = len(tasks)
        completed = sum(1 for t in tasks if t.status == "completed")
        failed = sum(1 for t in tasks if t.status == "failed")
        running = sum(1 for t in tasks if t.status == "running")
        pending = total - completed - failed - running

        return {
            "type": "status",
            "run_id": run_id,
            "status": run.status,
            "progress": {
                "total": total,
                "completed": completed,
                "failed": failed,
                "running": running,
                "pending": pending,
                "percentage": round(completed / total * 100) if total > 0 else 0,
            },
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        }
    finally:
        session.close()


@router.websocket("/ws/runs/{run_id}")
async def websocket_run_updates(websocket: WebSocket, run_id: int):
    """WebSocket endpoint for run progress updates."""
    await manager.connect(websocket, run_id)

    try:
        # Send initial status
        status = await get_run_status(run_id)
        await websocket.send_json(status)

        # Keep connection alive and send periodic updates
        while True:
            try:
                # Wait for message or timeout after 3 seconds
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=3.0
                )

                # Handle ping/pong
                if data == "ping":
                    await websocket.send_text("pong")

            except asyncio.TimeoutError:
                # Send periodic status update
                status = await get_run_status(run_id)
                await websocket.send_json(status)

                # Stop if run is completed/failed
                if status.get("status") in ("completed", "failed"):
                    await websocket.close()
                    break

    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket, run_id)


# Export function to broadcast updates from run manager
async def notify_run_update(run_id: int, update: dict):
    """Notify all WebSocket connections about a run update."""
    await manager.broadcast(run_id, update)
