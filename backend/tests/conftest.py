import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.espn import parse_scoreboard, parse_summary
from app.main import app

FIX = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIX / name).read_text())


@pytest.fixture
def summary_detail():
    return parse_summary("401700001", load("summary.json"))


@pytest.fixture
def scoreboard_games():
    return parse_scoreboard(load("scoreboard.json"))


class FakeEspn:
    """Stands in for EspnClient so tests never touch the network."""

    async def scoreboard(self, date=None):
        return parse_scoreboard(load("scoreboard.json"))

    async def game(self, event_id):
        return parse_summary(event_id, load("summary.json"))

    async def aclose(self):
        pass


@pytest.fixture
def client():
    with TestClient(app) as c:
        app.state.espn = FakeEspn()
        yield c
