"""Tests against a real ESPN response: the 2026 national championship game,
UConn at Michigan (69-63), saved as tests/fixtures/real_final.json.

ESPN's own box score includes "Lead Changes" and "Largest Lead", so we can
check our play-by-play analysis against ESPN's numbers.
"""

import pytest

from app.analysis import analyze
from app.espn import parse_summary
from tests.conftest import load

MICH, CONN = "130", "41"


@pytest.fixture(scope="module")
def final():
    return parse_summary("401856600", load("real_final.json"))


def espn_stat(detail, team_id, abbr):
    return next(s.value for s in detail.team_stats[team_id] if s.abbreviation == abbr)


def test_header(final):
    g = final.game
    assert (g.home.short_name, g.home.score) == ("Michigan", 69)
    assert (g.away.short_name, g.away.score) == ("UConn", 63)
    assert g.status.state == "post"
    assert g.home.logo and g.home.logo.startswith("https://")


def test_box_score(final):
    assert len(final.players) == 17
    assert len(final.plays) == 482
    assert espn_stat(final, MICH, "FG") == "21-55"
    assert espn_stat(final, MICH, "REB") == "39"
    cadeau = next(p for p in final.players if p.name == "Elliot Cadeau")
    assert cadeau.stats["PTS"] == "19"


def test_scores_never_decrease(final):
    scoring = [p for p in final.plays if p.scoring]
    for a, b in zip(scoring, scoring[1:], strict=False):
        assert b.home_score >= a.home_score and b.away_score >= a.away_score
    assert (scoring[-1].home_score, scoring[-1].away_score) == (69, 63)


def test_analysis_matches_espn(final):
    a = analyze(final)
    assert a.lead_changes == int(espn_stat(final, MICH, "LC"))  # 6
    assert a.largest_lead[MICH] == int(espn_stat(final, MICH, "LL"))  # 11
    assert a.largest_lead[CONN] == int(espn_stat(final, CONN, "LL"))  # 3
    assert a.shooting[MICH]["fg_pct"] == pytest.approx(21 / 55)
    assert a.top_scorers[0].name == "Elliot Cadeau"
    assert a.summary.startswith("Michigan beat UConn 69-63.")
