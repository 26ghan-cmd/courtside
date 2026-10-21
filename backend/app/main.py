"""Courtside API.

Run locally:  uvicorn app.main:app --reload
Docs:         http://localhost:8000/docs
"""

from __future__ import annotations

import re
from contextlib import asynccontextmanager
from pathlib import Path
from string import Template

import httpx
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .analysis import analyze
from .espn import EspnClient
from .matching import match_game
from .models import Analysis, GameDetail, GameListing
from .replay import replay
from .rooms import RoomManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.espn = EspnClient()
    app.state.rooms = RoomManager()
    yield
    await app.state.espn.aclose()


app = FastAPI(title="Courtside", version="1.0.0", lifespan=lifespan)
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


ReplayAt = Query(None, ge=0, description="Replay mode: the game as of its first N plays")


@app.get("/games/{game_id}", response_model=GameDetail)
async def game_detail(game_id: str, at: int | None = ReplayAt):
    if not re.fullmatch(r"\d+", game_id):
        raise HTTPException(400, "game_id must be numeric")
    detail = await _upstream(espn().game(game_id))
    return detail if at is None else replay(detail, at)


@app.get("/games/{game_id}/analysis", response_model=Analysis)
async def game_analysis(game_id: str, at: int | None = ReplayAt):
    return analyze(await game_detail(game_id, at))


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


JOIN_PAGE = Template((Path(__file__).parent / "join.html").read_text())


@app.get("/join/{room_id}", response_class=HTMLResponse)
async def join_page(room_id: str):
    """Invite link target. With Courtside installed, the extension reads the
    code from this page and joins the room when its side panel opens."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", room_id):
        raise HTTPException(404, "Room not found")
    room = app.state.rooms.get(room_id)
    if room:
        title, lead = "You're invited to a Courtside watch party", (
            "Open the Courtside side panel (click its icon in Chrome's toolbar) "
            "and you'll join this room automatically. Or enter the code yourself:")
        status = "Don't have Courtside yet? Ask whoever sent this link for the extension."
    else:
        title, lead = "This room has closed", (
            "Rooms close when the server restarts. Ask your friend to start a new one.")
        status = ""
    page = JOIN_PAGE.substitute(title=title, lead=lead, room_id=room_id, status=status,
                                open="1" if room else "0")
    return HTMLResponse(page, status_code=200 if room else 404)


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
