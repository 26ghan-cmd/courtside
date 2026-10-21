"""Replay mode: rebuild a finished game as it stood after its first N plays.

Used for development and demos while there are no live games: the side panel
steps N forward to make a finished game look live.

From play-by-play we can rebuild exactly: the score, clock, period, team
shooting (FG, 3PT, FT) and each player's points. Other box-score stats
(rebounds, assists, ...) aren't rebuilt and are left out of the snapshot.
"""

from __future__ import annotations

from collections import defaultdict

from .models import GameDetail, GameStatus, PlayerLine, TeamStat


def _period_name(n: int) -> str:
    if n <= 0:
        return ""
    if n <= 2:
        return ("1st", "2nd")[n - 1] + " Half"
    return "OT" if n == 3 else f"{n - 2}OT"


def replay(detail: GameDetail, at: int) -> GameDetail:
    """Snapshot of `detail` after its first `at` plays. Any `at` at or past the
    end still rebuilds the stats from plays, so tests can compare against ESPN."""
    at = max(0, min(at, len(detail.plays)))
    plays = detail.plays[:at]
    g = detail.game
    last = plays[-1] if plays else None
    finished = at == len(detail.plays) and g.status.state == "post"

    if finished:
        status = g.status
    elif last is None:
        status = GameStatus(state="pre", detail="Replay: tip-off")
    else:
        name = last.period_name or _period_name(last.period)
        status = GameStatus(state="in", period=last.period, clock=last.clock,
                            detail=f"{last.clock} - {name}")

    home_score = last.home_score if last else 0
    away_score = last.away_score if last else 0
    game = g.model_copy(update={
        "status": status,
        "home": g.home.model_copy(update={"score": home_score}),
        "away": g.away.model_copy(update={"score": away_score}),
    })

    # [made, attempted] per team per shot type
    shots: dict[str, dict[str, list[int]]] = defaultdict(
        lambda: {"FG": [0, 0], "3PT": [0, 0], "FT": [0, 0]})
    points: dict[str, int] = defaultdict(int)
    for p in plays:
        if not p.shooting or not p.team_id:
            continue
        made = int(p.scoring)
        kinds = ["FT"] if p.points_attempted == 1 else ["FG"]
        if p.points_attempted == 3:
            kinds.append("3PT")
        for k in kinds:
            shots[p.team_id][k][0] += made
            shots[p.team_id][k][1] += 1
        if p.scoring and p.athlete_id:
            points[p.athlete_id] += p.score_value

    def line(tid: str, k: str) -> TeamStat:
        made, att = shots[tid][k]
        return TeamStat(name=k, label=k, abbreviation=k, value=f"{made}-{att}")

    team_stats = {tid: [line(tid, k) for k in ("FG", "3PT", "FT")]
                  for tid in (g.home.id, g.away.id)}
    players = [
        PlayerLine(team_id=pl.team_id, name=pl.name, athlete_id=pl.athlete_id,
                   starter=pl.starter, stats={"PTS": str(points.get(pl.athlete_id, 0))})
        for pl in detail.players
    ]
    return GameDetail(game=game, team_stats=team_stats, players=players, plays=plays,
                      total_plays=len(detail.plays), replay_at=at)
