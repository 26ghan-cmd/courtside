# Courtside 🏀

A Chrome extension for watching college basketball. While you watch a stream, it shows:

- **Live stats:** the scorebug, team and player box scores, and play-by-play
- **Analysis:** an auto-written game summary, lead changes, scoring runs, and shooting splits
- **Watch-party chat:** start a room, share the code, and chat with friends during the game

More features are coming soon. Very exciting!

Stats come from ESPN's public (unofficial) college basketball endpoints.

## Layout

```
backend/     Python FastAPI service: stats proxy and cache, analysis, WebSocket chat rooms
extension/   Chrome MV3 extension in TypeScript: content script, background worker, side panel
ROADMAP.md   Plan: v1 by Nov 1, v2 by March Madness 2027
```

## Run it locally

**Quick start:** run `bash setup.sh` from this folder. It installs everything, runs the tests, builds the extension, and prints the next steps. The manual steps are below.

**Backend** (Python 3.11+):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
uvicorn app.main:app --reload       # → http://localhost:8000/docs
```

**Extension** (Node 18+):

```bash
cd extension
npm install
npm run build                        # outputs to extension/dist
```

Then open `chrome://extensions`, turn on **Developer mode**, click **Load unpacked**, and choose `extension/dist`.
Click the Courtside toolbar icon to open the side panel.

## How it works

1. `content.ts` runs on supported streaming sites and sends the page title to the background worker.
2. `background.ts` calls `GET /games/match?q=<title>`. The backend fuzzy-matches the title against today's scoreboard and saves the game it finds for that tab.
3. The side panel polls `GET /games/{id}` and `/games/{id}/analysis` every 15 seconds.
4. Chat goes through `WS /rooms/{room_id}/ws?name=...`. The protocol is documented in `backend/app/rooms.py`.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/games?date=YYYYMMDD` | All Division I games on a date |
| GET | `/games/match?q=...` | Find the game a page title refers to |
| GET | `/games/{id}` | Box score and play-by-play |
| GET | `/games/{id}/analysis` | Summary, runs, lead changes, shooting |
| POST | `/rooms` | Create a chat room |
| WS | `/rooms/{id}/ws?name=` | Join a room |
