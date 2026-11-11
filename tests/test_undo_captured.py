"""Undo together with the captured-pieces display (view()["captured"])."""

import copy

import session as session_module
from session import Session


def play(session, *moves):
    for source, target in moves:
        session.dispatch({"action": "move", "source": source, "target": target})


def captured(session):
    return session.view()["captured"]


def undo(session):
    return session.dispatch({"action": "undo"})


def test_nothing_is_captured_at_the_start_and_after_undoing_plain_moves():
    session = Session()
    assert captured(session) == []
    play(session, ("e2", "e4"), ("e7", "e5"))
    assert captured(session) == []
    undo(session)
    assert captured(session) == []


def test_undoing_a_capture_removes_the_piece_from_the_display():
    session = Session()
    play(session, ("e2", "e4"), ("d7", "d5"), ("e4", "d5"))
    assert captured(session) == ["bP"]
    undo(session)
    assert captured(session) == []
    assert session.view()["board"]["d5"] == "bP"


def test_undo_removes_only_the_last_capture():
    session = Session()
    play(session, ("e2", "e4"), ("d7", "d5"), ("e4", "d5"), ("d8", "d5"))
    assert captured(session) == ["bP", "wP"]
    undo(session)
    assert captured(session) == ["bP"]
    undo(session)
    assert captured(session) == []


def test_undoing_a_plain_move_keeps_earlier_captures_displayed():
    session = Session()
    play(session, ("e2", "e4"), ("d7", "d5"), ("e4", "d5"), ("g8", "f6"))
    assert captured(session) == ["bP"]
    undo(session)
    assert captured(session) == ["bP"]


def test_the_display_matches_each_earlier_position_while_undoing():
    session = Session()
    game = [("e2", "e4"), ("e7", "e5"), ("g1", "f3"), ("b8", "c6"), ("f1", "c4"),
            ("g8", "f6"), ("f3", "g5"), ("d7", "d5"), ("e4", "d5"), ("f6", "d5")]
    shown = [[]]
    for step in game:
        play(session, step)
        shown.append(copy.deepcopy(captured(session)))
    assert shown[-1] == ["bP", "wP"]
    for played in range(len(game) - 1, -1, -1):
        undo(session)
        assert captured(session) == shown[played]


def test_against_the_computer_undo_removes_both_captures(monkeypatch):
    replies = iter([("d7", "d5"), ("d8", "d5")])
    monkeypatch.setattr(session_module, "choose_move", lambda position: next(replies))
    session = Session("computer")
    play(session, ("e2", "e4"))
    session.dispatch({"action": "computer-move"})
    play(session, ("e4", "d5"))
    session.dispatch({"action": "computer-move"})
    assert captured(session) == ["bP", "wP"]
    view = undo(session)
    assert view["captured"] == []
    assert view["moves"] == ["e2-e4", "d7-d5"]
    assert view["turn"] == "w"


def test_a_capture_after_undoing_one_is_shown_once():
    session = Session()
    play(session, ("e2", "e4"), ("d7", "d5"), ("e4", "d5"))
    undo(session)
    play(session, ("e4", "d5"))
    assert captured(session) == ["bP"]


def test_new_game_clears_the_display_after_an_undo():
    session = Session()
    play(session, ("e2", "e4"), ("d7", "d5"), ("e4", "d5"))
    undo(session)
    play(session, ("e4", "d5"))
    session.dispatch({"action": "new"})
    assert captured(session) == []
