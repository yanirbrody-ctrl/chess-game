"""Undo together with the rest of the game: check, checkmate, the computer, history."""

import copy

import pytest

import session as session_module
from game import new_position
from session import Session


def play(session, *moves):
    for source, target in moves:
        session.dispatch({"action": "move", "source": source, "target": target})


def test_undoing_a_move_that_gave_check_clears_the_check():
    session = Session()
    play(session, ("e2", "e4"), ("f7", "f6"), ("d1", "h5"))
    assert session.view()["status"] == "check"
    assert session.view()["moves"][-1] == "d1-h5+"
    view = session.dispatch({"action": "undo"})
    assert view["status"] is None
    assert view["turn"] == "w"
    assert view["board"]["d1"] == "wQ" and "h5" not in view["board"]


def test_undoing_checkmate_reopens_the_game():
    session = Session()
    play(session, ("f2", "f3"), ("e7", "e5"), ("g2", "g4"), ("d8", "h4"))
    view = session.view()
    assert view["status"] == "checkmate" and view["winner"] == "Black"
    assert view["moves"][-1] == "d8-h4#"
    view = session.dispatch({"action": "undo"})
    assert view["status"] is None and view["winner"] is None
    assert view["turn"] == "b"
    assert view["board"]["d8"] == "bQ"
    # Black may now choose another move instead of the mating one.
    play(session, ("g8", "f6"))
    assert session.view()["status"] is None


def test_after_undo_the_moved_piece_has_its_old_legal_moves_again():
    session = Session()
    play(session, ("e2", "e4"))
    assert session.dispatch({"action": "legal", "source": "e2"})["targets"] == []
    session.dispatch({"action": "undo"})
    targets = session.dispatch({"action": "legal", "source": "e2"})["targets"]
    assert set(targets) == {"e3", "e4"}


def test_undoing_every_move_walks_back_through_each_earlier_position():
    session = Session()
    game = [("e2", "e4"), ("e7", "e5"), ("g1", "f3"), ("b8", "c6"), ("f1", "c4"),
            ("g8", "f6"), ("f3", "g5"), ("d7", "d5"), ("e4", "d5")]
    boards = [copy.deepcopy(new_position()[0])]
    for source, target in game:
        play(session, (source, target))
        boards.append(copy.deepcopy(session.view()["board"]))
    for played in range(len(game) - 1, -1, -1):
        view = session.dispatch({"action": "undo"})
        assert view["board"] == boards[played]
        assert len(view["moves"]) == played
    assert session.view()["moves"] == []
    assert session.view()["turn"] == "w"
    assert session.history == []
    assert len(session.redo) == len(game)


def test_each_undo_removes_exactly_one_move_label():
    session = Session()
    play(session, ("e2", "e4"), ("e7", "e5"), ("g1", "f3"))
    counts = []
    for _ in range(3):
        counts.append(len(session.dispatch({"action": "undo"})["moves"]))
    assert counts == [2, 1, 0]


def test_a_stored_snapshot_is_not_changed_by_later_play():
    session = Session()
    play(session, ("e2", "e4"), ("e7", "e5"))
    session.dispatch({"action": "undo"})
    play(session, ("d7", "d5"))
    assert "d5" not in session.history[0]["after"][0]
    assert session.history[0]["before"] == new_position()
    assert session.position[0] is not session.history[0]["after"][0]


def test_repeated_undo_at_the_beginning_is_harmless():
    session = Session()
    for _ in range(3):
        view = session.dispatch({"action": "undo"})
    assert view["board"] == new_position()[0]
    assert view["can_undo"] is False and view["undo_preview"] is None
    assert session.history == [] and session.redo == []


def test_against_the_computer_it_is_the_players_turn_after_undo():
    session = Session("computer")
    play(session, ("e2", "e4"))
    session.dispatch({"action": "computer-move"})
    session.dispatch({"action": "undo"})
    assert session.computer_to_move() is False
    with pytest.raises(ValueError):
        session.dispatch({"action": "computer-move"})
    play(session, ("d2", "d4"))
    assert session.computer_to_move() is True


def test_against_the_computer_two_undos_return_to_the_start():
    session = Session("computer")
    for source, target in (("e2", "e4"), ("d2", "d4")):
        play(session, (source, target))
        session.dispatch({"action": "computer-move"})
    assert len(session.view()["moves"]) == 4
    session.dispatch({"action": "undo"})
    assert len(session.view()["moves"]) == 2
    view = session.dispatch({"action": "undo"})
    assert view["board"] == new_position()[0]
    assert view["turn"] == "w" and view["moves"] == []
    assert view["can_undo"] is False


def test_against_the_computer_undo_after_the_players_mate_takes_back_one_move(monkeypatch):
    replies = iter([("e7", "e5"), ("b8", "c6"), ("g8", "f6")])
    monkeypatch.setattr(session_module, "choose_move", lambda position: next(replies))
    session = Session("computer")
    for source, target in (("e2", "e4"), ("f1", "c4"), ("d1", "h5")):
        play(session, (source, target))
        session.dispatch({"action": "computer-move"})
    play(session, ("h5", "f7"))
    view = session.view()
    assert view["status"] == "checkmate" and view["winner"] == "White"
    assert len(view["moves"]) == 7
    view = session.dispatch({"action": "undo"})
    assert len(view["moves"]) == 6
    assert view["status"] is None and view["turn"] == "w"
    assert view["board"]["h5"] == "wQ" and view["board"]["f7"] == "bP"
