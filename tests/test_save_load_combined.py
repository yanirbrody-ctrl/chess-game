"""Save/load together with undo, captured pieces and promotion.

The partner's tests already cover undo with save/load in detail; these cover what the
three features do together.
"""

import json

import pytest

from session import Session

PROMOTION_SETUP_MOVES = 8


def save_text(session):
    return json.dumps(session.dispatch({"action": "save"})["save"])


def load_text(text, opponent="human"):
    fresh = Session(opponent)
    fresh.dispatch({"action": "load", "data": text})
    return fresh


def play(session, *moves):
    for source, target in moves:
        session.dispatch({"action": "move", "source": source, "target": target})


def undo(session):
    return session.dispatch({"action": "undo"})


def promoted_session():
    session = Session()
    session.dispatch({"action": "promotion-setup"})
    session.dispatch({"action": "move", "source": "b7", "target": "a8", "promotion": "Q"})
    return session


def test_the_undo_preview_survives_save_and_load():
    session = Session()
    play(session, ("e2", "e4"), ("d7", "d5"), ("e4", "d5"))
    loaded = load_text(save_text(session))
    assert loaded.view()["undo_preview"] == session.view()["undo_preview"]
    assert loaded.view()["can_undo"] is True


def test_a_new_move_after_loading_and_undoing_discards_redo():
    session = Session()
    play(session, ("e2", "e4"), ("e7", "e5"))
    loaded = load_text(save_text(session))
    undo(loaded)
    assert len(loaded.redo) == 1
    play(loaded, ("d7", "d5"))
    assert loaded.redo == []
    assert loaded.view()["moves"] == ["e2-e4", "d7-d5"]


def test_loading_replaces_the_current_game_and_its_undo_history():
    saved = Session()
    play(saved, ("e2", "e4"), ("e7", "e5"))
    current = Session()
    play(current, ("d2", "d4"), ("d7", "d5"), ("c2", "c4"))
    current.dispatch({"action": "load", "data": save_text(saved)})
    assert current.view()["moves"] == ["e2-e4", "e7-e5"]
    view = undo(current)
    assert view["moves"] == ["e2-e4"]
    assert view["board"]["d2"] == "wP" and "d4" not in view["board"]


def test_new_game_after_loading_clears_undo_and_redo():
    session = Session()
    play(session, ("e2", "e4"), ("e7", "e5"))
    undo(session)
    loaded = load_text(save_text(session))
    loaded.dispatch({"action": "new"})
    assert loaded.history == [] and loaded.redo == []
    assert loaded.view()["captured"] == []


def test_the_captured_display_survives_save_and_load():
    session = Session()
    play(session, ("e2", "e4"), ("d7", "d5"), ("e4", "d5"), ("d8", "d5"))
    loaded = load_text(save_text(session))
    assert loaded.view()["captured"] == ["bP", "wP"]


def test_undoing_a_capture_after_loading_updates_the_captured_display():
    session = Session()
    play(session, ("e2", "e4"), ("d7", "d5"), ("e4", "d5"))
    loaded = load_text(save_text(session))
    view = undo(loaded)
    assert view["captured"] == []
    assert view["board"]["d5"] == "bP"


def test_the_captured_display_is_right_for_a_game_saved_after_an_undo():
    session = Session()
    play(session, ("e2", "e4"), ("d7", "d5"), ("e4", "d5"))
    undo(session)
    loaded = load_text(save_text(session))
    assert loaded.view()["captured"] == []
    assert len(loaded.redo) == 1


def test_a_promotion_survives_save_and_load():
    session = promoted_session()
    loaded = load_text(save_text(session))
    view = loaded.view()
    assert view["board"]["a8"] == "wQ" and "b7" not in view["board"]
    assert view["moves"][-1] == "b7xa8=Q"
    assert view["captured"] == ["bP", "wP", "bR"]
    assert loaded.history[-1]["promotion"] == "Q"


def test_undoing_a_loaded_promotion_restores_the_pawn_and_the_rook():
    loaded = load_text(save_text(promoted_session()))
    view = undo(loaded)
    assert view["board"]["b7"] == "wP" and view["board"]["a8"] == "bR"
    assert view["captured"] == ["bP", "wP"]
    assert view["turn"] == "w" and len(view["moves"]) == PROMOTION_SETUP_MOVES


def test_the_undo_preview_of_a_loaded_promotion_returns_the_pawn():
    loaded = load_text(save_text(promoted_session()))
    assert loaded.view()["undo_preview"]["moves"][0] == {
        "label": "b7xa8=Q", "source": "b7", "target": "a8", "piece": "wP", "captured": "bR"}


def test_an_undone_promotion_keeps_its_chosen_piece_in_the_redo_list():
    session = promoted_session()
    undo(session)
    saved = json.loads(save_text(session))
    assert saved["redo"] == [{"source": "b7", "target": "a8", "promotion": "Q"}]
    loaded = load_text(json.dumps(saved))
    assert loaded.redo[0]["promotion"] == "Q"
    assert loaded.redo[0]["label"] == "b7xa8=Q"
    assert loaded.view()["board"]["b7"] == "wP"


def test_the_promotion_choice_is_saved_only_for_the_promoting_move():
    saved = json.loads(save_text(promoted_session()))
    assert saved["history"][-1] == {"source": "b7", "target": "a8", "promotion": "Q"}
    assert all(set(record) == {"source", "target"}
               for record in saved["history"][:-1])


def test_a_save_that_lost_the_promotion_choice_is_rejected_and_changes_nothing():
    saved = json.loads(save_text(promoted_session()))
    del saved["history"][-1]["promotion"]
    session = Session()
    play(session, ("e2", "e4"))
    with pytest.raises(ValueError, match="Invalid save file"):
        session.dispatch({"action": "load", "data": json.dumps(saved)})
    assert session.view()["moves"] == ["e2-e4"]


def test_a_promotion_game_can_continue_after_loading():
    loaded = load_text(save_text(promoted_session()))
    loaded.dispatch({"action": "move", "source": "g2", "target": "h1", "promotion": "N"})
    view = loaded.view()
    assert view["board"]["h1"] == "bN"
    assert view["moves"][-1].startswith("g2xh1=N")
    assert loaded.redo == []
