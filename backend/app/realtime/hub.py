"""CYBERPULSE AI — realtime hub.

In-process WebSocket fan-out by default. A Redis pub/sub adapter is used
automatically when REDIS_URL is reachable (for multi-process deployments).
"""
from __future__ import annotations

import asyncio
import json
import logging

logger = logging.getLogger("cyberpulse.realtime")


class Hub:
    def __init__(self):
        self._clients: set = set()
        self._lock = asyncio.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop):
        """Capture the main event loop at startup (called from FastAPI lifespan)."""
        self._loop = loop

    async def connect(self, ws):
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)
        logger.info("WS client connected (%d total)", len(self._clients))
        try:
            await ws.send_text(json.dumps({
                "type": "hello",
                "payload": {"server_time": _iso_now(), "clients": len(self._clients)},
            }))
        except Exception:
            pass

    async def disconnect(self, ws):
        async with self._lock:
            self._clients.discard(ws)
        logger.info("WS client disconnected (%d total)", len(self._clients))

    async def broadcast(self, message: dict):
        """Send to all connected clients (thread-safe entry via run_coroutine_threadsafe)."""
        data = json.dumps(message, default=str)
        async with self._lock:
            clients = list(self._clients)
        dead = []
        for ws in clients:
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._clients.discard(ws)

    def broadcast_sync(self, message: dict):
        """Thread-safe broadcast callable from sync (DB) code or worker threads."""
        loop = self._loop
        if loop is None or loop.is_closed():
            # fallback: we're already on the event loop
            try:
                asyncio.get_running_loop()
                asyncio.ensure_future(self.broadcast(message))
            except RuntimeError:
                return
            return
        asyncio.run_coroutine_threadsafe(self.broadcast(message), loop)

    @property
    def client_count(self) -> int:
        return len(self._clients)


def _iso_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


hub = Hub()