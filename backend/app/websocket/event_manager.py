from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any, Dict, Optional, Set

from fastapi import WebSocket


class EventManager:
    """
    Tracks per-user websocket connections and publishes job/status events.

    Events are always JSON objects and are scoped by `user_id`.
    """

    def __init__(self) -> None:
        self._connections: Dict[str, Set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[user_id].add(websocket)

    async def disconnect(self, websocket: WebSocket, user_id: str) -> None:
        async with self._lock:
            sockets = self._connections.get(user_id)
            if not sockets:
                return
            sockets.discard(websocket)
            if not sockets:
                self._connections.pop(user_id, None)

    async def emit_user_event(self, user_id: str, payload: Dict[str, Any]) -> None:
        async with self._lock:
            targets = list(self._connections.get(user_id, set()))

        if not targets:
            return

        dead: list[WebSocket] = []
        message = dict(payload)
        message.setdefault("user_id", user_id)

        for ws in targets:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)

        if not dead:
            return

        async with self._lock:
            sockets = self._connections.get(user_id)
            if not sockets:
                return
            for ws in dead:
                sockets.discard(ws)
            if not sockets:
                self._connections.pop(user_id, None)

    def emit_user_event_threadsafe(self, user_id: str, payload: Dict[str, Any]) -> None:
        """
        Safe to call from worker threads; schedules async send on app event loop.
        """
        if self._loop is None:
            return
        try:
            asyncio.run_coroutine_threadsafe(
                self.emit_user_event(user_id, payload),
                self._loop,
            )
        except Exception:
            # Event publishing should never crash worker threads.
            pass


event_manager = EventManager()

