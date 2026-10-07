"""In-memory watch-party rooms over WebSockets.

Message protocol (JSON, both directions):
  client -> server  {"type": "chat", "text": "..."}
  server -> client  {"type": "chat", "user": "...", "text": "...", "ts": 1730000000.0}
                    {"type": "presence", "users": ["alice", "bob"]}
                    {"type": "history", "messages": [...]}
                    {"type": "error", "message": "..."}

Later: add {"type": "signal", ...} relays here for WebRTC voice/video,
and swap the in-memory store for Redis if you deploy more than one server.
"""

from __future__ import annotations

import secrets
import time
from collections import deque
from dataclasses import dataclass, field

from starlette.websockets import WebSocket

HISTORY = 100
MAX_TEXT = 500


@dataclass
class Room:
    id: str
    game_id: str | None = None
    members: dict[WebSocket, str] = field(default_factory=dict)
    history: deque = field(default_factory=lambda: deque(maxlen=HISTORY))

    def users(self) -> list[str]:
        return sorted(self.members.values())


class RoomManager:
    def __init__(self) -> None:
        self.rooms: dict[str, Room] = {}

    def create(self, game_id: str | None = None) -> Room:
        rid = secrets.token_urlsafe(6)
        room = self.rooms[rid] = Room(id=rid, game_id=game_id)
        return room

    def get(self, rid: str) -> Room | None:
        return self.rooms.get(rid)

    async def join(self, room: Room, ws: WebSocket, name: str) -> None:
        taken = set(room.members.values())
        base, n = name, 2
        while name in taken:
            name, n = f"{base}{n}", n + 1
        room.members[ws] = name
        await ws.send_json({"type": "history", "messages": list(room.history)})
        await self.broadcast(room, {"type": "presence", "users": room.users()})

    async def leave(self, room: Room, ws: WebSocket) -> None:
        room.members.pop(ws, None)
        if room.members:
            await self.broadcast(room, {"type": "presence", "users": room.users()})

    async def chat(self, room: Room, ws: WebSocket, text: str) -> None:
        text = text.strip()[:MAX_TEXT]
        if not text:
            return
        msg = {"type": "chat", "user": room.members[ws], "text": text, "ts": time.time()}
        room.history.append(msg)
        await self.broadcast(room, msg)

    async def broadcast(self, room: Room, msg: dict) -> None:
        dead = []
        for ws in list(room.members):
            try:
                await ws.send_json(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            room.members.pop(ws, None)
