"""Normalized data models. Everything the extension sees goes through these,
so the rest of the app never depends on ESPN's raw JSON shape."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

GameState = Literal["pre", "in", "post"]


class Team(BaseModel):
    id: str
    name: str  # "Villanova Wildcats"
    short_name: str  # "Villanova"
    abbreviation: str  # "VILL"
    logo: str | None = None
    score: int = 0
    home: bool = False


class GameStatus(BaseModel):
    state: GameState
    period: int = 0
    clock: str = ""
    detail: str = ""  # "Halftime", "Final", "7:42 - 2nd Half"


class GameListing(BaseModel):
    id: str
    name: str
    start: str  # ISO timestamp
    status: GameStatus
    home: Team
    away: Team


class TeamStat(BaseModel):
    name: str  # machine name, e.g. "fieldGoalsMade-fieldGoalsAttempted"
    label: str  # display label, e.g. "Rebounds"
    abbreviation: str = ""  # short form, e.g. "REB" (falls back to label)
    value: str  # "25-58"


class PlayerLine(BaseModel):
    team_id: str
    name: str
    athlete_id: str = ""
    starter: bool = False
    stats: dict[str, str]  # label -> value, e.g. {"PTS": "18", "MIN": "31"}


class Play(BaseModel):
    id: str
    period: int
    clock: str
    text: str
    team_id: str | None = None
    scoring: bool = False
    score_value: int = 0
    home_score: int = 0
    away_score: int = 0
    period_name: str = ""  # "1st Half", "OT"
    shooting: bool = False  # a shot or free throw attempt
    points_attempted: int = 0  # 1 = free throw, 2 or 3 = field goal
    athlete_id: str | None = None  # shooter, for shooting plays


class GameDetail(BaseModel):
    game: GameListing
    team_stats: dict[str, list[TeamStat]]  # team_id -> stats
    players: list[PlayerLine]
    plays: list[Play]
    total_plays: int = 0  # plays in the full game (differs from len(plays) in replay)
    replay_at: int | None = None  # set when this is a replayed snapshot


class Run(BaseModel):
    team_id: str
    points: int
    opponent_points: int
    start_play_id: str
    end_play_id: str
    period: int


class Analysis(BaseModel):
    game_id: str
    lead_changes: int
    ties: int
    largest_lead: dict[str, int]  # team_id -> largest lead
    runs: list[Run]
    shooting: dict[str, dict[str, float | None]]  # team_id -> {"fg_pct": .., "three_pct": ..}
    top_scorers: list[PlayerLine]
    summary: str
