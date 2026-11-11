"""Save/load and undo working together."""

import json

from session import Session

OPENING = [("e2", "e4"), ("d7", "d5"), ("e4", "d5"), ("g8", "f6"), ("f1", "b5")]


def played(moves=OPENING, opponent="human"):
    session = Session(opponent)
    for source, target in moves:
        session.play(source, target)
    return session


def reloaded(session):
    """A fresh session loaded from session's save file."""
    fresh = Session()
    text = json.dumps(session.dispatch({"action": "save"})["save"])
    fresh.dispatch({"action": "load", "data": text})
    return fresh


def snapshot(session):
    return session.position, session.notation, session.history, session.redo


def test_undo_after_load_takes_back_a_capture_made_before_saving():
    original = played(OPENING[:3])
    fresh = reloaded(original)
    view = fresh.dispatch({"action": "undo"})
    assert view["board"]["d5"] == "bP" and view["board"]["e4"] == "wP"
    assert view["turn"] == "w" and view["moves"] == ["e2-e4", "d7-d5"]
    original.undo()
    assert snapshot(fresh) == snapshot(original)


def test_against_the_computer_undo_after_load_takes_back_the_reply_too():
    original = played(OPENING[:2], "computer")
    fresh = reloaded(original)
    view = fresh.dispatch({"action": "undo"})
    assert view["moves"] == [] and view["turn"] == "w"
    assert len(fresh.redo) == 2


def test_against_the_computer_undo_after_loading_before_the_reply_takes_back_one():
    fresh = reloaded(played(OPENING[:1], "computer"))
    view = fresh.dispatch({"action": "undo"})
    assert view["moves"] == [] and view["turn"] == "w"
    assert len(fresh.redo) == 1


def test_loaded_game_offers_the_same_undo_as_the_original():
    original = played(OPENING, "computer")
    fresh = reloaded(original)
    assert fresh.view()["can_undo"] is True
    assert fresh.view()["undo_preview"] == original.view()["undo_preview"]


def test_undone_moves_survive_save_and_load():
    original = played()
    original.undo()
    original.undo()
    fresh = reloaded(original)
    assert snapshot(fresh) == snapshot(original)
    assert [entry["label"] for entry in fresh.redo] == ["f1-b5+", "g8-f6"]


def test_undo_to_the_start_then_save_and_load():
    original = played()
    for _ in OPENING:
        original.undo()
    fresh = reloaded(original)
    assert fresh.history == [] and fresh.view()["can_undo"] is False
    assert snapshot(fresh) == snapshot(original)
    assert len(fresh.redo) == len(OPENING)


def test_undo_after_load_continues_the_redo_list():
    original = played()
    original.undo()
    fresh = reloaded(original)
    fresh.undo()
    original.undo()
    assert snapshot(fresh) == snapshot(original)


def test_save_file_holds_plain_move_records():
    original = played()
    original.undo()
    saved = original.dispatch({"action": "save"})["save"]
    for record in saved["history"] + saved["redo"]:
        assert set(record) == {"source", "target"}
