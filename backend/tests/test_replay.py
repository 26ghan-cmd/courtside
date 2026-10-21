"""Replay mode, checked against the real 2026 championship game."""

import pytest

from app.analysis import analyze
from app.espn import parse_summary
from app.replay import replay
from tests.conftest import load

MICH, CONN = "130", "41"
HALFTIME = 208  # plays[207] is "End of 1st half"


@pytest.fixture(scope="module")
def final():
    return parse_summary("401856600", load("real_final.json"))


def stat(detail, team_id, abbr):
    return next(s.value for s in detail.team_stats[team_id] if s.abbreviation == abbr)


def pts(detail, name):
    return next(p.stats["PTS"] for p in detail.players if p.name == name)


def test_tipoff(final):
    r = replay(final, 0)
    assert r.game.status.state == "pre"
    assert (r.game.home.score, r.game.away.score) == (0, 0)
    assert r.plays == [] and r.total_plays == 482 and r.replay_at == 0


def test_halftime_matches_linescore(final):
    r = replay(final, HALFTIME)
    assert (r.game.home.score, r.game.away.score) == (33, 29)  # ESPN's 1st-half linescore
    assert r.game.status.state == "in"
    assert r.game.status.detail.endswith("1st Half")
    assert analyze(r).summary.startswith("Michigan leads UConn 33-29")


def test_full_rebuild_matches_espn_box_score(final):
    r = replay(final, len(final.plays))
    for tid in (MICH, CONN):
        for abbr in ("FG", "3PT", "FT"):
            assert stat(r, tid, abbr) == stat(final, tid, abbr), (tid, abbr)
    for p in final.players:
        assert pts(r, p.name) == p.stats["PTS"], p.name
    assert r.game.status.state == "post"


def test_out_of_range_is_clamped(final):
    assert replay(final, 10_000).replay_at == 482
    assert replay(final, -5).replay_at == 0


def test_points_only_increase(final):
    prev = 0
    for at in range(0, 483, 40):
        total = sum(int(p.stats["PTS"]) for p in replay(final, at).players)
        assert total >= prev
        prev = total
