from app.matching import match_game


def test_matches_both_teams(scoreboard_games):
    g = match_game("Providence vs. Villanova | Watch ESPN", scoreboard_games)
    assert g and g.id == "401700001"


def test_full_names_and_similar_schools(scoreboard_games):
    g = match_game("Kansas State Wildcats at Kansas Jayhawks - FOX Sports", scoreboard_games)
    assert g and g.id == "401700002"


def test_single_team_fallback(scoreboard_games):
    g = match_game("Villanova Basketball Live", scoreboard_games)
    assert g and g.id == "401700001"


def test_no_match(scoreboard_games):
    assert match_game("Cooking with Gordon", scoreboard_games) is None
