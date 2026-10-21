"""Match a streaming page's title/metadata to a game on today's scoreboard.

Stream pages usually expose text like "UConn vs. St. John's | Watch ESPN".
We look for each team's names in that text, then pick the game where both
teams appear.

Two details make this work for real team names:

* Normalizing: "St. John's" / "Saint John's" / "St Johns" all become "st johns",
  "Miami (OH)" becomes "miami oh", "Texas A&M" becomes "texas am".
* Shadowing: a short name inside a longer one doesn't count for a different
  team. In "Michigan State vs. Michigan", the first "Michigan" belongs to
  Michigan State, so only the second one counts for Michigan. Same for
  Kansas / Kansas State, Penn / Penn State, Miami / Miami (OH).
"""

from __future__ import annotations

import re

from .models import GameListing, Team

# Extra names people (and broadcasters) use, keyed by ESPN team id.
ALIASES: dict[str, list[str]] = {
    "41": ["connecticut"],                                   # UConn
    "2599": ["saint johns"],                                 # St. John's
    "193": ["miami ohio", "miami oh redhawks"],              # Miami (OH)
    "2390": ["miami fl", "miami florida", "miami fla"],      # Miami (FL)
    "153": ["unc", "tar heels"],                             # North Carolina
    "152": ["north carolina state"],                         # NC State
    "145": ["mississippi"],                                  # Ole Miss
    "221": ["pitt"],                                         # Pittsburgh
    "219": ["penn"],                                         # Pennsylvania
    "30": ["southern california", "southern cal"],           # USC
    "99": ["louisiana state"],                               # LSU
    "252": ["brigham young"],                                # BYU
    "2670": ["virginia commonwealth"],                       # VCU
    "2116": ["central florida"],                             # UCF
    "2567": ["southern methodist"],                          # SMU
    "2628": ["texas christian"],                             # TCU
    "232": ["college of charleston"],                        # Charleston
    "2306": ["k state"],                                     # Kansas State
    "2350": ["loyola il"],                                   # Loyola Chicago
    "2608": ["st marys ca"],                                 # Saint Mary's
}

# Abbreviations that are ordinary words in page text ("Don't miss...").
AMBIGUOUS_ABBREVIATIONS = {"miss", "more", "ball", "wake"}


def normalize(s: str) -> str:
    s = s.lower().replace("&", "").replace("'", "").replace("’", "").replace(".", "")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\bsaint\b", "st", s)
    return re.sub(r"\s+", " ", s).strip()


def variants(team: Team) -> set[str]:
    names = {team.name, team.short_name, team.location}
    if len(team.abbreviation) >= 3 and team.abbreviation.lower() not in AMBIGUOUS_ABBREVIATIONS:
        names.add(team.abbreviation)
    names.update(ALIASES.get(team.id, []))
    return {n for n in (normalize(x) for x in names if x) if n}


def _occurrences(text: str, games: list[GameListing]) -> list[tuple[int, int, str]]:
    """(start, end, team_id) for every team-name occurrence in normalized text."""
    found = []
    for g in games:
        for team in (g.home, g.away):
            for v in variants(team):
                for m in re.finditer(rf"(?<![a-z0-9]){re.escape(v)}(?![a-z0-9])", text):
                    found.append((m.start(), m.end(), team.id))
    return found


def team_scores(text: str, games: list[GameListing]) -> dict[str, float]:
    """Best match strength per team id, ignoring shadowed occurrences."""
    occ = _occurrences(normalize(text), games)
    scores: dict[str, float] = {}
    for s, e, tid in occ:
        shadowed = any(
            s2 <= s and e <= e2 and (e2 - s2) > (e - s) and tid2 != tid
            for s2, e2, tid2 in occ
        )
        if not shadowed:
            # Longer matches are more specific ("north carolina" beats "unc").
            scores[tid] = max(scores.get(tid, 0.0), 1.0 + (e - s) / 100)
    return scores


def match_game(text: str, games: list[GameListing]) -> GameListing | None:
    """Best game whose BOTH teams appear in text; falls back to a single-team
    match only if exactly one game matches that way."""
    scores = team_scores(text, games)
    scored = []
    for g in games:
        h, a = scores.get(g.home.id, 0.0), scores.get(g.away.id, 0.0)
        scored.append((h > 0 and a > 0, h + a, g))
    both = [s for s in scored if s[0]]
    if both:
        return max(both, key=lambda s: s[1])[2]
    one = [s for s in scored if s[1] > 0]
    return one[0][2] if len(one) == 1 else None
