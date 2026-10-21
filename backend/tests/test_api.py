def test_games(client):
    r = client.get("/games")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_match(client):
    r = client.get("/games/match", params={"q": "Providence @ Villanova"})
    assert r.json()["id"] == "401700001"


def test_detail_and_analysis(client):
    assert client.get("/games/401700001").json()["game"]["home"]["abbreviation"] == "VILL"
    assert client.get("/games/401700001/analysis").json()["lead_changes"] == 4
    assert client.get("/games/abc").status_code == 400


def test_replay_endpoints(client):
    r = client.get("/games/401700001", params={"at": 4}).json()
    assert r["replay_at"] == 4 and len(r["plays"]) == 4 and r["total_plays"] == 24
    assert (r["game"]["home"]["score"], r["game"]["away"]["score"]) == (3, 2)
    assert r["game"]["status"]["state"] == "in"
    a = client.get("/games/401700001/analysis", params={"at": 4}).json()
    assert a["summary"].startswith("Villanova leads Providence 3-2")
    assert client.get("/games/401700001", params={"at": -1}).status_code == 422


def test_chat_room(client):
    room = client.post("/rooms", json={"game_id": "401700001"}).json()
    with client.websocket_connect(f"/rooms/{room['id']}/ws?name=grant") as a:
        assert a.receive_json() == {"type": "history", "messages": []}
        assert a.receive_json()["users"] == ["grant"]

        with client.websocket_connect(f"/rooms/{room['id']}/ws?name=grant") as b:
            b.receive_json()  # history
            # duplicate names get a suffix
            assert b.receive_json()["users"] == ["grant", "grant2"]
            assert a.receive_json()["users"] == ["grant", "grant2"]

            b.send_json({"type": "chat", "text": "  what a three!  "})
            for ws in (a, b):
                m = ws.receive_json()
                assert (m["user"], m["text"]) == ("grant2", "what a three!")

        assert a.receive_json() == {"type": "presence", "users": ["grant"]}


def test_missing_room(client):
    with client.websocket_connect("/rooms/nope/ws") as ws:
        assert ws.receive_json()["type"] == "error"


def test_join_page(client):
    room = client.post("/rooms", json={}).json()
    r = client.get(f"/join/{room['id']}")
    assert r.status_code == 200 and room["id"] in r.text and "invited" in r.text
    gone = client.get("/join/nope123")
    assert gone.status_code == 404 and "closed" in gone.text
    assert client.get("/join/<script>").status_code == 404
