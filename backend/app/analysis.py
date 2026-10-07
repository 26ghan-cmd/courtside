"""Game analysis computed from normalized play-by-play and box score data.

Everything here is pure (no I/O) so it's easy to unit test and extend.
Ideas for later: win probability, pace/possessions, per-half splits,
"clutch" stats in the final 5 minutes.
"""

from __future__ import annotations

from .models import Analysis, GameDetail, PlayerLine, Run, TeamStat

MIN_RUN = 7  # unanswered points to count as a "run"


def _sign(x: int) -> int:
    return (x > 0) - (x < 0)


def lead_stats(detail: GameDetail) -> tuple[int, int, dict[str, int]]:
    """Returns (lead_changes, ties, largest_lead_by_team_id)."""
    home, away = detail.game.home.id, detail.game.away.id
    largest = {home: 0, away: 0}
    changes = ties = 0
    last_leader = 0  # +1 home, -1 away, 0 none yet
    prev_margin = 0
    for p in detail.plays:
        if not p.scoring:
            continue
        margin = p.home_score - p.away_score
        s = _sign(margin)
        if s != 0:
            if last_leader != 0 and s != last_leader:
                changes += 1
            last_leader = s
        elif prev_margin != 0:
            ties += 1
        prev_margin = margin
        if margin > 0:
            largest[home] = max(largest[home], margin)
        elif margin < 0:
            largest[away] = max(largest[away], -margin)
    return changes, ties, largest


def scoring_runs(detail: GameDetail, min_points: int = MIN_RUN) -> list[Run]:
    """Unanswered scoring streaks of at least `min_points`."""
    runs: list[Run] = []
    cur_team: str | None = None
    pts = 0
    start = end = ""
    period = 0

    def flush() -> None:
        if cur_team and pts >= min_points:
            runs.append(Run(team_id=cur_team, points=pts, opponent_points=0,
                            start_play_id=start, end_play_id=end, period=period))

    for p in detail.plays:
        if not p.scoring or not p.team_id or p.score_value <= 0:
            continue
        if p.team_id == cur_team:
            pts += p.score_value
            end = p.id
        else:
            flush()
            cur_team, pts, start, end, period = p.team_id, p.score_value, p.id, p.id, p.period
    flush()
    return sorted(runs, key=lambda r: r.points, reverse=True)


def _pct(stats: list[TeamStat], made_attempted: str, pct_abbr: str) -> float | None:
    """Prefer exact made/attempted ("21-55"); fall back to ESPN's rounded percentage."""
    by_key = {}
    for st in stats:
        by_key.setdefault(st.abbreviation, st.value)
        by_key.setdefault(st.label, st.value)
    ma = by_key.get(made_attempted)
    if ma and "-" in ma:
        made, att = (int(x) for x in ma.split("-", 1))
        return made / att if att else None
    try:
        v = float(by_key[pct_abbr])
        return v / 100 if v > 1 else v
    except (KeyError, ValueError):
        return None


def shooting(detail: GameDetail) -> dict[str, dict[str, float | None]]:
    return {
        tid: {
            "fg_pct": _pct(stats, "FG", "FG%"),
            "three_pct": _pct(stats, "3PT", "3P%"),
            "ft_pct": _pct(stats, "FT", "FT%"),
        }
        for tid, stats in detail.team_stats.items()
    }


def top_scorers(detail: GameDetail, n: int = 3) -> list[PlayerLine]:
    def pts(p: PlayerLine) -> int:
        try:
            return int(p.stats.get("PTS", 0))
        except ValueError:
            return 0

    return sorted(detail.players, key=pts, reverse=True)[:n]


def write_summary(detail: GameDetail, changes: int, ties: int,
                  runs: list[Run], scorers: list[PlayerLine]) -> str:
    g = detail.game
    names = {g.home.id: g.home.short_name, g.away.id: g.away.short_name}
    leader, trailer = (g.home, g.away) if g.home.score >= g.away.score else (g.away, g.home)

    if g.status.state == "pre":
        return f"{g.away.short_name} at {g.home.short_name} hasn't tipped off yet."

    verb = "beat" if g.status.state == "post" else "leads"
    if leader.score == trailer.score:
        lines = [f"{leader.short_name} and {trailer.short_name} are tied "
                 f"{leader.score}-{trailer.score} ({g.status.detail})."]
    else:
        lines = [f"{leader.short_name} {verb} {trailer.short_name} "
                 f"{leader.score}-{trailer.score}"
                 + ("." if g.status.state == "post" else f" ({g.status.detail}).")]

    if changes:
        lines.append(f"The lead changed hands {changes} times with {ties} ties.")
    if runs:
        r = runs[0]
        lines.append(f"Biggest run: a {r.points}-0 burst by {names.get(r.team_id, '?')} "
                     f"in period {r.period}.")
    if scorers:
        s = scorers[0]
        lines.append(f"{s.name} ({names.get(s.team_id, '?')}) leads all scorers with "
                     f"{s.stats.get('PTS', '?')} points.")
    return " ".join(lines)


def analyze(detail: GameDetail) -> Analysis:
    changes, ties, largest = lead_stats(detail)
    runs = scoring_runs(detail)
    scorers = top_scorers(detail)
    return Analysis(
        game_id=detail.game.id,
        lead_changes=changes,
        ties=ties,
        largest_lead=largest,
        runs=runs,
        shooting=shooting(detail),
        top_scorers=scorers,
        summary=write_summary(detail, changes, ties, runs, scorers),
    )
