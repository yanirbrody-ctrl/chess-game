"""Undo together with pawn promotion and the captured-pieces display."""

import copy

import session as session_module
from session import Session


def move(session, source, target, promotion=None):
    action = {"action": "move", "source": source, "target": target}
    if promotion:
        action["promotion"] = promotion
    return session.dispatch(action)


def undo(session):
    return session.dispatch({"action": "undo"})


def setup_session():
    """White to move, and b7 can capture the rook on a8 and promote."""
    session = Session()
    session.dispatch({"action": "promotion-setup"})
    return session


def quiet_promotion_session(extra=None):
    session = Session()
    board = {"a1": "wK", "h6": "bK", "d7": "wP"}
    board.update(extra or {})
    session.position = [board, "w"]
    return session


def test_promoting_changes_the_pawn_into_the_chosen_piece():
    session = setup_session()
    view = move(session, "b7", "a8", "Q")
    assert view["board"]["a8"] == "wQ" and "b7" not in view["board"]
    assert view["moves"][-1] == "b7xa8=Q"


def test_undoing_a_promotion_brings_back_the_pawn_and_the_captured_piece():
    session = setup_session()
    before = copy.deepcopy(session.view())
    move(session, "b7", "a8", "Q")
    view = undo(session)
    assert view["board"] == before["board"]
    assert view["board"]["b7"] == "wP" and view["board"]["a8"] == "bR"
    assert view["turn"] == "w"
    assert view["moves"] == before["moves"]


def test_after_undoing_a_promotion_another_piece_can_be_chosen():
    session = setup_session()
    move(session, "b7", "a8", "Q")
    undo(session)
    view = move(session, "b7", "a8", "N")
    assert view["board"]["a8"] == "wN"
    assert view["moves"][-1] == "b7xa8=N"
    assert session.redo == []


def test_the_promotion_choices_are_offered_again_after_undo():
    session = setup_session()
    move(session, "b7", "a8", "Q")
    undo(session)
    legal = session.dispatch({"action": "legal", "source": "b7"})
    assert "a8" in legal["promotions"]


def test_a_promotion_without_capture_is_not_shown_as_a_capture():
    session = quiet_promotion_session()
    view = move(session, "d7", "d8", "Q")
    assert view["board"]["d8"] == "wQ"
    assert view["captured"] == []
    assert view["moves"] == ["d7-d8=Q"]


def test_undoing_a_promotion_without_capture_restores_the_pawn():
    session = quiet_promotion_session()
    move(session, "d7", "d8", "Q")
    view = undo(session)
    assert view["board"]["d7"] == "wP" and "d8" not in view["board"]
    assert view["captured"] == [] and view["turn"] == "w"


def test_a_promotion_that_captures_shows_only_the_captured_piece():
    session = setup_session()
    assert session.view()["captured"] == ["bP", "wP"]
    view = move(session, "b7", "a8", "Q")
    assert view["captured"] == ["bP", "wP", "bR"]
    view = undo(session)
    assert view["captured"] == ["bP", "wP"]


def test_a_captured_promoted_piece_is_shown_as_the_piece_it_had_become():
    session = quiet_promotion_session({"e1": "wK", "a6": "bK", "h8": "bR"})
    del session.position[0]["a1"], session.position[0]["h6"]
    move(session, "d7", "d8", "Q")
    view = move(session, "h8", "d8")
    assert view["captured"] == ["wQ"]
    view = undo(session)
    assert view["captured"] == []
    assert view["board"]["d8"] == "wQ"
    view = undo(session)
    assert view["board"]["d7"] == "wP" and "d8" not in view["board"]


def test_the_undo_preview_of_a_promotion_returns_the_pawn():
    session = setup_session()
    move(session, "b7", "a8", "Q")
    preview = session.view()["undo_preview"]["moves"][0]
    assert preview == {"label": "b7xa8=Q", "source": "b7", "target": "a8",
                       "piece": "wP", "captured": "bR"}


def test_against_the_computer_undo_takes_back_a_promotion_and_the_reply(monkeypatch):
    monkeypatch.setattr(session_module, "choose_move", lambda position: ("h8", "d8"))
    session = Session("computer")
    session.position = [{"e1": "wK", "a6": "bK", "d7": "wP", "h8": "bR"}, "w"]
    move(session, "d7", "d8", "Q")
    session.dispatch({"action": "computer-move"})
    assert session.view()["captured"] == ["wQ"]
    view = undo(session)
    assert view["board"] == {"e1": "wK", "a6": "bK", "d7": "wP", "h8": "bR"}
    assert view["turn"] == "w" and view["moves"] == [] and view["captured"] == []


def test_new_game_after_a_promotion_clears_everything():
    session = setup_session()
    move(session, "b7", "a8", "Q")
    session.dispatch({"action": "new"})
    view = undo(session)
    assert view["captured"] == [] and view["moves"] == []
