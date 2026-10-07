"""Generates small synthetic fixtures shaped like ESPN's API responses.

Replace these with real captures once you can hit the API:
    curl "$ESPN_BASE/summary?event=<id>" > summary.json   # ESPN_BASE: see app/espn.py
"""

import json
from pathlib import Path

HERE = Path(__file__).parent

HOME = {"id": "222", "displayName": "Villanova Wildcats", "shortDisplayName": "Villanova",
        "abbreviation": "VILL", "location": "Villanova"}
AWAY = {"id": "2507", "displayName": "Providence Friars", "shortDisplayName": "Providence",
        "abbreviation": "PROV", "location": "Providence"}


def competitors(hs, as_):
    return [
        {"id": HOME["id"], "homeAway": "home", "score": str(hs), "team": HOME},
        {"id": AWAY["id"], "homeAway": "away", "score": str(as_), "team": AWAY},
    ]


def status(state, period, clock, detail):
    return {"period": period, "displayClock": clock,
            "type": {"state": state, "shortDetail": detail, "detail": detail}}


# (team, points) scoring sequence. Includes a 9-0 Villanova run and a lead change.
SEQ = [("A", 2), ("H", 3), ("A", 3), ("H", 2), ("H", 2), ("H", 3), ("H", 2),
       ("A", 2), ("A", 3), ("A", 3), ("H", 1), ("A", 2)]


def plays():
    out, hs, as_ = [], 0, 0
    for i, (who, pts) in enumerate(SEQ):
        team = HOME if who == "H" else AWAY
        if who == "H":
            hs += pts
        else:
            as_ += pts
        out.append({"id": str(1000 + i), "period": {"number": 1 if i < 6 else 2},
                    "clock": {"displayValue": f"{19 - i}:00"},
                    "text": f"{team['shortDisplayName']} scores {pts}",
                    "team": {"id": team["id"]}, "scoringPlay": True, "scoreValue": pts,
                    "homeScore": hs, "awayScore": as_})
        out.append({"id": str(2000 + i), "period": {"number": 1 if i < 6 else 2},
                    "clock": {"displayValue": f"{19 - i}:30"}, "text": "Defensive rebound",
                    "team": {"id": team["id"]}, "scoringPlay": False, "scoreValue": 0,
                    "homeScore": hs, "awayScore": as_})
    return out, hs, as_


def main():
    ps, hs, as_ = plays()
    summary = {
        "header": {"competitions": [{"date": "2026-03-01T17:00Z",
                                     "competitors": competitors(hs, as_),
                                     "status": status("post", 2, "0:00", "Final")}]},
        "boxscore": {
            "teams": [
                {"team": HOME, "statistics": [
                    {"name": "fieldGoalsMade-fieldGoalsAttempted", "label": "FG",
                     "displayValue": "6-12"},
                    {"name": "fieldGoalPct", "label": "Field Goal %", "abbreviation": "FG%",
                     "displayValue": "50"},
                    {"name": "threePointFieldGoalsMade-threePointFieldGoalsAttempted",
                     "label": "3PT", "displayValue": "2-5"}]},
                {"team": AWAY, "statistics": [
                    {"name": "fieldGoalsMade-fieldGoalsAttempted", "label": "FG",
                     "displayValue": "7-15"},
                    {"name": "threePointFieldGoalsMade-threePointFieldGoalsAttempted",
                     "label": "3PT", "displayValue": "3-6"}]},
            ],
            "players": [
                {"team": HOME, "statistics": [{"labels": ["MIN", "PTS", "REB", "AST"],
                 "athletes": [
                     {"athlete": {"displayName": "Jordan Hart"}, "starter": True,
                      "stats": ["32", "9", "4", "3"]},
                     {"athlete": {"displayName": "Sam Lee"}, "starter": True,
                      "stats": ["28", "4", "7", "1"]},
                     {"athlete": {"displayName": "Bench Guy"}, "didNotPlay": True,
                      "stats": []}]}]},
                {"team": AWAY, "statistics": [{"labels": ["MIN", "PTS", "REB", "AST"],
                 "athletes": [
                     {"athlete": {"displayName": "Chris Vale"}, "starter": True,
                      "stats": ["35", "11", "5", "2"]},
                     {"athlete": {"displayName": "Max Ortiz"}, "starter": False,
                      "stats": ["20", "4", "2", "4"]}]}]},
            ],
        },
        "plays": ps,
    }
    scoreboard = {"events": [
        {"id": "401700001", "name": "Providence Friars at Villanova Wildcats",
         "date": "2026-03-01T17:00Z",
         "competitions": [{"competitors": competitors(hs, as_),
                           "status": status("post", 2, "0:00", "Final")}]},
        {"id": "401700002", "name": "Kansas State Wildcats at Kansas Jayhawks",
         "date": "2026-03-01T20:00Z",
         "competitions": [{"competitors": [
             {"id": "2305", "homeAway": "home", "score": "0",
              "team": {"id": "2305", "displayName": "Kansas Jayhawks",
                       "shortDisplayName": "Kansas", "abbreviation": "KU"}},
             {"id": "2306", "homeAway": "away", "score": "0",
              "team": {"id": "2306", "displayName": "Kansas State Wildcats",
                       "shortDisplayName": "Kansas St", "abbreviation": "KSU"}}],
             "status": status("pre", 0, "0:00", "3/1 - 3:00 PM EST")}]},
    ]}
    (HERE / "summary.json").write_text(json.dumps(summary, indent=1))
    (HERE / "scoreboard.json").write_text(json.dumps(scoreboard, indent=1))


if __name__ == "__main__":
    main()
