import pytest

from game import new_position
from session import Session


def play(session, *moves):
    for source, target in moves:
        session.dispatch({"action": "move", "source": source, "target": target})


def test_undo_returns_the_moved_piece_and_the_turn():
    session = Session()
    play(session, ("e2", "e4"))
    view = session.dispatch({"action": "undo"})
    assert view["board"] == new_position()[0]
    assert view["turn"] == "w"
    assert view["moves"] == []


def test_after_undo_the_player_can_move_a_different_piece():
    session = Session()
    play(session, ("e2", "e4"))
    session.dispatch({"action": "undo"})
    view = session.dispatch({"action": "move", "source": "d2", "target": "d4"})
    assert view["board"]["d4"] == "wP"
    assert view["board"]["e2"] == "wP"
    assert "e4" not in view["board"]
    assert view["moves"] == ["d2-d4"]


def test_undo_cancels_only_the_last_move_each_time():
    session = Session()
    play(session, ("e2", "e4"), ("e7", "e5"), ("g1", "f3"))
    view = session.dispatch({"action": "undo"})
    assert view["moves"] == ["e2-e4", "e7-e5"]
    assert view["turn"] == "w"
    assert view["board"]["g1"] == "wN" and "f3" not in view["board"]
    view = session.dispatch({"action": "undo"})
    assert view["moves"] == ["e2-e4"]
    assert view["turn"] == "b"


def test_undoing_a_capture_brings_back_the_captured_piece():
    session = Session()
    pieces_at_start = len(session.view()["board"])
    play(session, ("e2", "e4"), ("d7", "d5"), ("e4", "d5"))
    pieces_after_capture = len(session.view()["board"])
    assert pieces_after_capture == pieces_at_start - 1
    view = session.dispatch({"action": "undo"})
    assert len(view["board"]) == pieces_after_capture + 1
    assert len(view["board"]) == pieces_at_start
    assert view["board"]["d5"] == "bP"
    assert view["board"]["e4"] == "wP"
    assert view["turn"] == "w"


def test_undo_at_the_beginning_does_nothing():
    session = Session()
    view = session.dispatch({"action": "undo"})
    assert view["board"] == new_position()[0]
    assert view["turn"] == "w"
    assert view["moves"] == []
    assert view["can_undo"] is False


def test_can_undo_reports_whether_there_is_a_move_to_take_back():
    session = Session()
    assert session.view()["can_undo"] is False
    play(session, ("e2", "e4"))
    assert session.view()["can_undo"] is True
    assert session.dispatch({"action": "undo"})["can_undo"] is False


def test_new_game_clears_the_undo_history():
    session = Session()
    play(session, ("e2", "e4"))
    session.dispatch({"action": "new"})
    view = session.dispatch({"action": "undo"})
    assert view["board"] == new_position()[0]
    assert view["moves"] == []


def test_a_rejected_move_leaves_nothing_to_undo():
    session = Session()
    with pytest.raises(ValueError):
        play(session, ("e2", "e5"))
    assert session.view()["can_undo"] is False


def test_history_holds_one_entry_per_move_played():
    session = Session()
    assert session.history == [] and session.redo == []
    play(session, ("e2", "e4"), ("e7", "e5"))
    assert [entry["label"] for entry in session.history] == ["e2-e4", "e7-e5"]
    first = session.history[0]
    assert first["before"] == new_position()
    assert first["after"][0]["e4"] == "wP" and first["after"][1] == "b"


def test_undo_moves_the_entry_from_history_to_redo():
    session = Session()
    play(session, ("e2", "e4"), ("e7", "e5"))
    session.dispatch({"action": "undo"})
    assert [entry["label"] for entry in session.history] == ["e2-e4"]
    assert [entry["label"] for entry in session.redo] == ["e7-e5"]
    session.dispatch({"action": "undo"})
    assert session.history == []
    assert [entry["label"] for entry in session.redo] == ["e7-e5", "e2-e4"]


def test_a_new_move_after_undo_discards_redo():
    session = Session()
    play(session, ("e2", "e4"))
    session.dispatch({"action": "undo"})
    assert len(session.redo) == 1
    play(session, ("d2", "d4"))
    assert session.redo == []


def test_new_game_clears_history_and_redo():
    session = Session()
    play(session, ("e2", "e4"), ("e7", "e5"))
    session.dispatch({"action": "undo"})
    session.dispatch({"action": "new"})
    assert session.history == [] and session.redo == []


def test_history_and_redo_can_be_saved_as_plain_json():
    import json
    session = Session()
    play(session, ("e2", "e4"), ("e7", "e5"))
    session.dispatch({"action": "undo"})
    saved = json.loads(json.dumps({"history": session.history, "redo": session.redo}))
    assert saved == {"history": session.history, "redo": session.redo}


def test_against_the_computer_undo_takes_back_both_moves():
    session = Session("computer")
    play(session, ("e2", "e4"))
    session.dispatch({"action": "computer-move"})
    assert len(session.view()["moves"]) == 2
    view = session.dispatch({"action": "undo"})
    assert view["board"] == new_position()[0]
    assert view["turn"] == "w"
    assert view["moves"] == []
    assert view["opponent"] == "computer"


def test_against_the_computer_undo_before_it_replies_takes_back_only_my_move():
    session = Session("computer")
    play(session, ("e2", "e4"))
    view = session.dispatch({"action": "undo"})
    assert view["board"] == new_position()[0]
    assert view["turn"] == "w"
    assert view["moves"] == []


def test_against_the_computer_undo_goes_back_to_my_previous_turn_only():
    session = Session("computer")
    play(session, ("e2", "e4"))
    session.dispatch({"action": "computer-move"})
    play(session, ("d2", "d4"))
    session.dispatch({"action": "computer-move"})
    view = session.dispatch({"action": "undo"})
    assert len(view["moves"]) == 2
    assert view["turn"] == "w"
    assert view["board"]["d2"] == "wP"
    assert view["board"]["e4"] == "wP"
