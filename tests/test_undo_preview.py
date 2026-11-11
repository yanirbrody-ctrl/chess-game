import json
import threading
import urllib.request

from server import make_server
from session import Session


def play(session, *moves):
    for source, target in moves:
        session.dispatch({"action": "move", "source": source, "target": target})


def preview(session):
    return session.view()["undo_preview"]


def test_there_is_no_preview_when_there_is_nothing_to_undo():
    session = Session()
    assert preview(session) is None
    play(session, ("e2", "e4"))
    session.dispatch({"action": "undo"})
    assert preview(session) is None


def test_preview_shows_the_move_undo_would_take_back():
    session = Session()
    play(session, ("g1", "f3"))
    assert preview(session) == {"moves": [
        {"label": "g1-f3", "source": "g1", "target": "f3",
         "piece": "wN", "captured": None}]}


def test_preview_covers_only_the_last_move_between_two_players():
    session = Session()
    play(session, ("e2", "e4"), ("e7", "e5"), ("g1", "f3"))
    moves = preview(session)["moves"]
    assert [m["label"] for m in moves] == ["g1-f3"]
    session.dispatch({"action": "undo"})
    assert [m["label"] for m in preview(session)["moves"]] == ["e7-e5"]


def test_preview_of_a_capture_names_the_captured_piece():
    session = Session()
    play(session, ("e2", "e4"), ("d7", "d5"), ("e4", "d5"))
    move = preview(session)["moves"][0]
    assert move["label"] == "e4xd5"
    assert move["source"] == "e4" and move["target"] == "d5"
    assert move["piece"] == "wP"
    assert move["captured"] == "bP"


def test_preview_against_the_computer_lists_its_reply_then_my_move():
    session = Session("computer")
    play(session, ("e2", "e4"))
    session.dispatch({"action": "computer-move"})
    moves = preview(session)["moves"]
    assert len(moves) == 2
    assert moves[0]["piece"][0] == "b"
    assert moves[1] == {"label": "e2-e4", "source": "e2", "target": "e4",
                        "piece": "wP", "captured": None}


def test_preview_against_the_computer_before_it_replies_is_only_my_move():
    session = Session("computer")
    play(session, ("e2", "e4"))
    moves = preview(session)["moves"]
    assert [m["label"] for m in moves] == ["e2-e4"]


def test_the_preview_matches_what_undo_actually_does():
    session = Session("computer")
    play(session, ("e2", "e4"))
    session.dispatch({"action": "computer-move"})
    play(session, ("d2", "d4"))
    session.dispatch({"action": "computer-move"})
    moves = preview(session)["moves"]
    after_board = session.dispatch({"action": "undo"})["board"]
    for move in moves:
        assert after_board[move["source"]] == move["piece"]
        if move["captured"]:
            assert after_board[move["target"]] == move["captured"]
    assert len(session.view()["moves"]) == 2


def test_history_entries_record_the_squares_of_each_move():
    session = Session()
    play(session, ("e2", "e4"), ("d7", "d5"), ("e4", "d5"))
    entry = session.history[2]
    assert (entry["source"], entry["target"]) == ("e4", "d5")
    assert entry["label"] == "e4xd5"


def test_the_preview_is_served_over_http_as_json():
    server = make_server(0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        def call(action):
            request = urllib.request.Request(
                base + "/api/action", data=json.dumps(action).encode(),
                headers={"Content-Type": "application/json"})
            return json.load(urllib.request.urlopen(request))

        assert call({"action": "new"})["undo_preview"] is None
        view = call({"action": "move", "source": "e2", "target": "e4"})
        assert view["undo_preview"]["moves"][0]["label"] == "e2-e4"
        state = json.load(urllib.request.urlopen(base + "/api/state"))
        assert state["undo_preview"] == view["undo_preview"]
    finally:
        server.shutdown()
        server.server_close()
