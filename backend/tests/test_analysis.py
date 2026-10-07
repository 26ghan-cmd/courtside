from app.analysis import analyze, lead_stats, scoring_runs


def test_parse_summary(summary_detail):
    g = summary_detail.game
    assert g.home.short_name == "Villanova" and g.home.home
    assert (g.home.score, g.away.score) == (13, 15)
    assert g.status.state == "post"
    # DNP players are skipped
    assert {p.name for p in summary_detail.players} == {
        "Jordan Hart", "Sam Lee", "Chris Vale", "Max Ortiz"}
    assert summary_detail.players[0].stats["PTS"] == "9"


def test_lead_changes_and_ties(summary_detail):
    changes, ties, largest = lead_stats(summary_detail)
    assert changes == 4
    assert ties == 2
    assert largest == {"222": 7, "2507": 2}


def test_runs(summary_detail):
    runs = scoring_runs(summary_detail)
    assert [(r.team_id, r.points) for r in runs] == [("222", 9), ("2507", 8)]


def test_analyze_summary_text(summary_detail):
    a = analyze(summary_detail)
    assert a.summary.startswith("Providence beat Villanova 15-13.")
    assert "9-0 burst by Villanova" in a.summary
    assert "Chris Vale" in a.summary
    assert a.shooting["222"]["fg_pct"] == 0.5  # computed from "6-12"
    assert a.shooting["2507"]["fg_pct"] == 7 / 15  # computed from "7-15"
