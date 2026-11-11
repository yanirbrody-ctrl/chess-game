import json
import threading
import urllib.error
import urllib.request

import pytest

from game import copy_position
from server import make_server
from session import Session

OPENING = [("e2", "e4"), ("d7", "d5"), ("e4", "d5"), ("g8", "f6"), ("f1", "b5")]


def played(moves=OPENING, opponent="human"):
    session = Session(opponent)
    for source, target in moves:
        session.play(source, target)
    return session


def save_text(session):
    return json.dumps(session.dispatch({"action": "save"})["save"])


def load(session, text):
    return session.dispatch({"action": "load", "data": text})


def test_history_records_each_move_and_new_game_clears_it():
    session = played(OPENING[:2])
    assert session.history == [{"source": "e2", "target": "e4"},
                                {"source": "d7", "target": "d5"}]
    assert session.redo == []
    session.dispatch({"action": "new"})
    assert session.history == [] and session.redo == []


def test_a_new_move_discards_redo():
    session = played(OPENING[:1])
    session.redo = [{"source": "d7", "target": "d5"}]
    session.dispatch({"action": "move", "source": "e7", "target": "e5"})
    assert session.redo == []


def test_save_file_contents():
    session = played()
    saved = session.dispatch({"action": "save"})["save"]
    assert saved["format"] == "aicode-chess-save" and saved["version"] == 1
    assert saved["opponent"] == "human"
    assert saved["history"] == [{"source": s, "target": t} for s, t in OPENING]
    assert saved["redo"] == []
    assert saved["position"] == {"board": session.position[0], "turn": "b"}
    assert saved["notation"] == session.notation


def test_load_restores_board_turn_notation_and_history_in_a_fresh_session():
    original = played()
    fresh = Session()
    view = load(fresh, save_text(original))
    assert fresh.position == original.position
    assert view["turn"] == "b"
    assert view["moves"] == ["e2-e4", "d7-d5", "e4xd5", "g8-f6", "f1-b5+"]
    assert view["status"] == "check"
    assert fresh.history == original.history


def test_saving_does_not_share_state_with_the_game():
    session = played(OPENING[:1])
    saved = session.dispatch({"action": "save"})["save"]
    session.play("e7", "e5")
    assert saved["notation"] == ["e2-e4"]
    assert "e5" not in saved["position"]["board"]


@pytest.mark.parametrize("opponent", ["human", "computer"])
def test_load_restores_the_opponent(opponent):
    fresh = Session("human" if opponent == "computer" else "computer")
    view = load(fresh, save_text(played(OPENING[:2], opponent)))
    assert view["opponent"] == opponent == fresh.opponent


def test_loaded_computer_game_continues():
    session = played(OPENING[:1], "computer")
    fresh = Session()
    load(fresh, save_text(session))
    assert fresh.computer_to_move()
    view = fresh.dispatch({"action": "computer-move"})
    assert view["turn"] == "w" and len(fresh.history) == 2


def test_redo_continuation_round_trips():
    session = played(OPENING[:3])
    session.redo = [{"source": "g8", "target": "f6"}, {"source": "f1", "target": "b5"}]
    fresh = Session()
    load(fresh, save_text(session))
    assert fresh.redo == session.redo
    assert fresh.history == session.history
    assert fresh.position == session.position


def test_play_after_load_extends_history():
    fresh = Session()
    load(fresh, save_text(played(OPENING[:2])))
    fresh.dispatch({"action": "move", "source": "b1", "target": "c3"})
    assert fresh.history[-1] == {"source": "b1", "target": "c3"}
    assert fresh.notation[-1] == "b1-c3"


def test_empty_game_round_trips():
    fresh = played(OPENING[:2])
    view = load(fresh, save_text(Session("computer")))
    assert fresh.history == [] and view["moves"] == [] and view["opponent"] == "computer"
    assert fresh.position == Session().position


def corrupt(change):
    def text():
        saved = json.loads(save_text(played()))
        change(saved)
        return json.dumps(saved)
    return text


BAD_SAVES = {
    "not json": lambda: "{not json",
    "empty": lambda: "",
    "not an object": lambda: "[1, 2]",
    "wrong format": corrupt(lambda s: s.update(format="something-else")),
    "future version": corrupt(lambda s: s.update(version=99)),
    "unknown opponent": corrupt(lambda s: s.update(opponent="robot")),
    "missing history": corrupt(lambda s: s.pop("history")),
    "history not a list": corrupt(lambda s: s.update(history="e2e4")),
    "move not an object": corrupt(lambda s: s["history"].__setitem__(0, "e2-e4")),
    "move missing target": corrupt(lambda s: s["history"][0].pop("target")),
    "move with extra field": corrupt(lambda s: s["history"][0].update(piece="wP")),
    "illegal move": corrupt(lambda s: s["history"][0].update(target="e5")),
    "off-board square": corrupt(lambda s: s["history"][0].update(target="e9")),
    "board mismatch": corrupt(lambda s: s["position"]["board"].pop("a1")),
    "turn mismatch": corrupt(lambda s: s["position"].update(turn="w")),
    "notation mismatch": corrupt(lambda s: s["notation"].__setitem__(0, "e2-e3")),
    "illegal redo": corrupt(lambda s: s.update(redo=[{"source": "a1", "target": "a8"}])),
    "redo not a list": corrupt(lambda s: s.update(redo=None)),
}


@pytest.mark.parametrize("make_text", BAD_SAVES.values(), ids=BAD_SAVES.keys())
def test_bad_saves_are_rejected_and_leave_the_game_unchanged(make_text):
    text = make_text()
    session = played(OPENING[:2], "computer")
    before = (copy_position(session.position), list(session.notation),
              list(session.history), session.opponent)
    with pytest.raises(ValueError, match="^Invalid save file"):
        load(session, text)
    assert before == (session.position, session.notation, session.history,
                      session.opponent)


@pytest.mark.parametrize("data", [None, 42, {"history": []}])
def test_load_needs_file_text(data):
    with pytest.raises(ValueError, match="^Invalid save file"):
        Session().dispatch({"action": "load", "data": data})


def post(server, action):
    request = urllib.request.Request(
        f"http://127.0.0.1:{server.server_port}/api/action",
        data=json.dumps(action).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def run_server():
    server = make_server(0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def test_save_and_load_across_server_restarts():
    first = run_server()
    try:
        post(first, {"action": "new", "opponent": "computer"})
        post(first, {"action": "move", "source": "e2", "target": "e4"})
        _, moved = post(first, {"action": "computer-move"})
        _, result = post(first, {"action": "save"})
    finally:
        first.shutdown()
        first.server_close()
    second = run_server()
    try:
        status, view = post(second, {"action": "load", "data": json.dumps(result["save"])})
        assert status == 200
        assert (view["board"], view["turn"], view["moves"], view["opponent"]) == (
            moved["board"], "w", moved["moves"], "computer")
        status, error = post(second, {"action": "load", "data": "{broken"})
        assert status == 400 and error["error"]
    finally:
        second.shutdown()
        second.server_close()
