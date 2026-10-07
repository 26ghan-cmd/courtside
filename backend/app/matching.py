"""Match a streaming page's title/metadata to a game on today's scoreboard.

Stream pages usually expose something like "Duke vs. North Carolina | Watch ESPN".
We score every game by how many of each team's name variants appear in the text.
"""

from __future__ import annotations

import re

from .models import GameListing, Team

STOPWORDS = {"state", "university", "college", "of", "the", "st", "at", "vs"}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", s.lower()).strip()


def _variants(t: Team) -> list[str]:
    out = {_norm(t.name), _norm(t.short_name)}
    if len(t.abbreviation) >= 3:
        out.add(_norm(t.abbreviation))
    return [v for v in out if v and v not in STOPWORDS]


def team_score(team: Team, text: str) -> float:
    padded = f" {_norm(text)} "
    best = 0.0
    for v in _variants(team):
        if f" {v} " in padded:
            # Longer matches are more specific ("north carolina" beats "unc").
            best = max(best, 1.0 + len(v) / 100)
    return best


def match_game(text: str, games: list[GameListing]) -> GameListing | None:
    """Best game whose BOTH teams appear in text; falls back to a single-team
    match only if exactly one game matches that way."""
    scored = []
    for g in games:
        h, a = team_score(g.home, text), team_score(g.away, text)
        scored.append((h > 0 and a > 0, h + a, g))
    both = [s for s in scored if s[0]]
    if both:
        return max(both, key=lambda s: s[1])[2]
    one = [s for s in scored if s[1] > 0]
    return one[0][2] if len(one) == 1 else None
