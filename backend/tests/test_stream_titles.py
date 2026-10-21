"""Stream detection against real ESPN team names (tests/fixtures/teams_subset.json,
taken from ESPN's team list) and the kinds of page titles streaming sites use."""

import pytest

from app.matching import match_game, normalize
from app.models import GameListing, GameStatus, Team
from tests.conftest import load

TEAMS = {t["displayName"]: t for t in load("teams_subset.json")}


def team(display: str, home: bool) -> Team:
    t = TEAMS[display]
    return Team(id=t["id"], name=t["displayName"], short_name=t["shortDisplayName"],
                abbreviation=t["abbreviation"], location=t["location"], home=home)


def game(away: str, home: str) -> GameListing:
    a, h = team(away, False), team(home, True)
    return GameListing(id=f"{a.id}@{h.id}", name=f"{away} at {home}", start="",
                       status=GameStatus(state="in"), home=h, away=a)


# One busy night of games, full of look-alike names.
SLATE = [
    game("UConn Huskies", "St. John's Red Storm"),
    game("Miami (OH) RedHawks", "Toledo Rockets"),
    game("Duke Blue Devils", "Miami Hurricanes"),
    game("Michigan State Spartans", "Michigan Wolverines"),
    game("Kansas State Wildcats", "Kansas Jayhawks"),
    game("NC State Wolfpack", "North Carolina Tar Heels"),
    game("Ole Miss Rebels", "Pittsburgh Panthers"),
    game("LSU Tigers", "Texas A&M Aggies"),
    game("Loyola Chicago Ramblers", "Saint Mary's Gaels"),
    game("Pennsylvania Quakers", "Villanova Wildcats"),
    game("Penn State Nittany Lions", "Kentucky Wildcats"),
]


def found(title: str) -> str | None:
    g = match_game(title, SLATE)
    return g.name if g else None


@pytest.mark.parametrize("title, expected", [
    ("Watch UConn vs. St. John's | ESPN+", "UConn Huskies at St. John's Red Storm"),
    ("Connecticut at Saint John's - College Basketball - FOX Sports",
     "UConn Huskies at St. John's Red Storm"),
    ("St Johns Red Storm vs UConn Huskies Live", "UConn Huskies at St. John's Red Storm"),
    ("Miami (OH) RedHawks at Toledo Rockets | ESPN+", "Miami (OH) RedHawks at Toledo Rockets"),
    ("Miami (Ohio) vs. Toledo", "Miami (OH) RedHawks at Toledo Rockets"),
    ("Duke at Miami - ACC Network", "Duke Blue Devils at Miami Hurricanes"),
    ("Michigan State vs. Michigan | Big Ten Network",
     "Michigan State Spartans at Michigan Wolverines"),
    ("Michigan vs Michigan St", "Michigan State Spartans at Michigan Wolverines"),
    ("Kansas State @ Kansas", "Kansas State Wildcats at Kansas Jayhawks"),
    ("NC State at North Carolina", "NC State Wolfpack at North Carolina Tar Heels"),
    ("UNC vs. N.C. State - Peacock", "NC State Wolfpack at North Carolina Tar Heels"),
    ("Ole Miss vs Pitt", "Ole Miss Rebels at Pittsburgh Panthers"),
    ("Texas A&M vs. LSU | SEC Network", "LSU Tigers at Texas A&M Aggies"),
    ("St. Mary's vs Loyola Chicago", "Loyola Chicago Ramblers at Saint Mary's Gaels"),
    ("Penn at Villanova", "Pennsylvania Quakers at Villanova Wildcats"),
    ("Penn State vs. Kentucky", "Penn State Nittany Lions at Kentucky Wildcats"),
    ("Michigan State Spartans Men's Basketball", "Michigan State Spartans at Michigan Wolverines"),
])
def test_titles(title, expected):
    assert found(title) == expected


@pytest.mark.parametrize("title", [
    "SportsCenter | Watch ESPN",
    "Don't miss tonight's college basketball action",
    "Watch live TV on YouTube TV",
    "Wildcats vs. Wildcats",  # three teams are called Wildcats tonight
])
def test_no_false_matches(title):
    assert found(title) is None


def test_normalize():
    assert normalize("St. John's") == normalize("Saint John’s") == "st johns"
    assert normalize("Miami (OH)") == "miami oh"
    assert normalize("Texas A&M") == "texas am"
