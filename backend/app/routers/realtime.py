"""CYBERPULSE AI — realtime WebSocket endpoint (/ws/events)."""
from __future__ import annotations

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..realtime.hub import hub

router = APIRouter(tags=["realtime"])


@router.websocket("/ws/events")
async def ws_events(ws: WebSocket):
    await hub.connect(ws)
    try:
        while True:
            # keep connection alive; client may send pings
            data = await ws.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await ws.send_text(json.dumps({"type": "pong"}))
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        await hub.disconnect(ws)
    except Exception:
        await hub.disconnect(ws)