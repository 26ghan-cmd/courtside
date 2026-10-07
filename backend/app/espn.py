"""Client for ESPN's public (unofficial, undocumented) men's college basketball API.

The endpoints are free and keyless but can change without notice, so all
parsing is defensive and isolated in the `parse_*` functions below. If ESPN
changes shape, only this file should need edits.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from .models import (
    GameDetail,
    GameListing,
    GameStatus,
    Play,
    PlayerLine,
    Team,
    TeamStat,
)

BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball"


def _int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


# --------------------------------------------------------------------------- parsing


def parse_team(c: dict) -> Team:
    t = c.get("team", {})
    return Team(
        id=str(t.get("id", c.get("id", ""))),
        name=t.get("displayName", ""),
        short_name=t.get("shortDisplayName") or t.get("location", ""),
        abbreviation=t.get("abbreviation", ""),
        logo=t.get("logo") or (t.get("logos") or [{}])[0].get("href"),
        score=_int(c.get("score")),
        home=c.get("homeAway") == "home",
    )


def parse_status(s: dict) -> GameStatus:
    st = s.get("type", {})
    return GameStatus(
        state=st.get("state", "pre"),
        period=_int(s.get("period")),
        clock=s.get("displayClock", ""),
        detail=st.get("shortDetail") or st.get("detail", ""),
    )


def parse_competition(event_id: str, name: str, date: str, comp: dict) -> GameListing:
    teams = [parse_team(c) for c in comp.get("competitors", [])]
    home = next((t for t in teams if t.home), teams[0])
    away = next((t for t in teams if not t.home), teams[-1])
    return GameListing(
        id=str(event_id),
        name=name,
        start=date,
        status=parse_status(comp.get("status", {})),
        home=home,
        away=away,
    )


def parse_scoreboard(data: dict) -> list[GameListing]:
    games = []
    for e in data.get("events", []):
        comp = (e.get("competitions") or [{}])[0]
        comp.setdefault("status", e.get("status", {}))
        games.append(parse_competition(e["id"], e.get("name", ""), e.get("date", ""), comp))
    return games


def parse_summary(event_id: str, data: dict) -> GameDetail:
    header = data.get("header", {})
    comp = (header.get("competitions") or [{}])[0]
    home_team = next(
        (c for c in comp.get("competitors", []) if c.get("homeAway") == "home"), {}
    )
    away_team = next(
        (c for c in comp.get("competitors", []) if c.get("homeAway") == "away"), {}
    )
    name = f"{away_team.get('team', {}).get('displayName', '?')} at " \
           f"{home_team.get('team', {}).get('displayName', '?')}"
    game = parse_competition(event_id, name, comp.get("date", ""), comp)

    box = data.get("boxscore", {})
    team_stats: dict[str, list[TeamStat]] = {}
    for t in box.get("teams", []):
        tid = str(t.get("team", {}).get("id", ""))
        team_stats[tid] = [
            TeamStat(
                name=s.get("name", ""),
                label=s.get("label") or s.get("abbreviation", ""),
                value=str(s.get("displayValue", "")),
            )
            for s in t.get("statistics", [])
        ]

    players: list[PlayerLine] = []
    for group in box.get("players", []):
        tid = str(group.get("team", {}).get("id", ""))
        for block in group.get("statistics", []):
            labels = block.get("labels") or block.get("names") or []
            for a in block.get("athletes", []):
                if a.get("didNotPlay"):
                    continue
                players.append(
                    PlayerLine(
                        team_id=tid,
                        name=a.get("athlete", {}).get("displayName", ""),
                        starter=bool(a.get("starter")),
                        stats=dict(zip(labels, a.get("stats", []), strict=False)),
                    )
                )

    plays = [
        Play(
            id=str(p.get("id", i)),
            period=_int(p.get("period", {}).get("number")),
            clock=p.get("clock", {}).get("displayValue", ""),
            text=p.get("text", ""),
            team_id=str(p["team"]["id"]) if p.get("team") else None,
            scoring=bool(p.get("scoringPlay")),
            score_value=_int(p.get("scoreValue")),
            home_score=_int(p.get("homeScore")),
            away_score=_int(p.get("awayScore")),
        )
        for i, p in enumerate(data.get("plays", []))
    ]

    return GameDetail(game=game, team_stats=team_stats, players=players, plays=plays)


# --------------------------------------------------------------------------- client


class EspnClient:
    """Thin async client with a small TTL cache so many viewers of one game
    don't multiply requests to ESPN."""

    def __init__(self, ttl_seconds: float = 10.0, http: httpx.AsyncClient | None = None):
        self.ttl = ttl_seconds
        self.http = http or httpx.AsyncClient(base_url=BASE, timeout=10.0)
        self._cache: dict[str, tuple[float, dict]] = {}

    async def _get(self, path: str, params: dict | None = None) -> dict:
        key = f"{path}?{sorted((params or {}).items())}"
        hit = self._cache.get(key)
        if hit and time.monotonic() - hit[0] < self.ttl:
            return hit[1]
        r = await self.http.get(path, params=params)
        r.raise_for_status()
        data = r.json()
        self._cache[key] = (time.monotonic(), data)
        return data

    async def scoreboard(self, date: str | None = None) -> list[GameListing]:
        """date: YYYYMMDD. groups=50 returns all Division I games, not just ranked ones."""
        params: dict[str, Any] = {"groups": 50, "limit": 400}
        if date:
            params["dates"] = date
        return parse_scoreboard(await self._get("/scoreboard", params))

    async def game(self, event_id: str) -> GameDetail:
        return parse_summary(event_id, await self._get("/summary", {"event": event_id}))

    async def aclose(self) -> None:
        await self.http.aclose()
