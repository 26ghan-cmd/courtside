"""Courtside API.

Run locally:  uvicorn app.main:app --reload
Docs:         http://localhost:8000/docs
"""

from __future__ import annotations

import re
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .analysis import analyze
from .espn import EspnClient
from .matching import match_game
from .models import Analysis, GameDetail, GameListing
from .rooms import RoomManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.espn = EspnClient()
    app.state.rooms = RoomManager()
    yield
    await app.state.espn.aclose()


app = FastAPI(title="Courtside", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^chrome-extension://.*$|^http://localhost(:\d+)?$",
    allow_methods=["*"],
    allow_headers=["*"],
)


def espn() -> EspnClient:
    return app.state.espn


async def _upstream(coro):
    try:
        return await coro
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"ESPN returned {e.response.status_code}") from e
    except httpx.HTTPError as e:
        raise HTTPException(503, "Could not reach ESPN") from e


# --------------------------------------------------------------------------- games


@app.get("/health")
async def health() -> dict:
    return {"ok": True}


@app.get("/games", response_model=list[GameListing])
async def list_games(date: str | None = Query(None, pattern=r"^\d{8}$")):
    """All D-I games on a date (YYYYMMDD), default today."""
    return await _upstream(espn().scoreboard(date))


@app.get("/games/match", response_model=GameListing | None)
async def match(q: str = Query(..., min_length=3), date: str | None = None):
    """Find the game a stream page is showing, from its title text."""
    return match_game(q, await _upstream(espn().scoreboard(date)))


@app.get("/games/{game_id}", response_model=GameDetail)
async def game_detail(game_id: str):
    if not re.fullmatch(r"\d+", game_id):
        raise HTTPException(400, "game_id must be numeric")
    return await _upstream(espn().game(game_id))


@app.get("/games/{game_id}/analysis", response_model=Analysis)
async def game_analysis(game_id: str):
    return analyze(await game_detail(game_id))


# --------------------------------------------------------------------------- rooms


class RoomCreate(BaseModel):
    game_id: str | None = None


@app.post("/rooms")
async def create_room(body: RoomCreate) -> dict:
    room = app.state.rooms.create(body.game_id)
    return {"id": room.id, "game_id": room.game_id}


@app.get("/rooms/{room_id}")
async def get_room(room_id: str) -> dict:
    room = app.state.rooms.get(room_id)
    if not room:
        raise HTTPException(404, "Room not found")
    return {"id": room.id, "game_id": room.game_id, "users": room.users()}


@app.websocket("/rooms/{room_id}/ws")
async def room_ws(ws: WebSocket, room_id: str, name: str = "guest"):
    rooms: RoomManager = app.state.rooms
    room = rooms.get(room_id)
    await ws.accept()
    if not room:
        await ws.send_json({"type": "error", "message": "Room not found"})
        await ws.close(code=4404)
        return
    await rooms.join(room, ws, name.strip()[:24] or "guest")
    try:
        while True:
            msg = await ws.receive_json()
            if msg.get("type") == "chat":
                await rooms.chat(room, ws, str(msg.get("text", "")))
    except WebSocketDisconnect:
        pass
    finally:
        await rooms.leave(room, ws)
