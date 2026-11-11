"""Undo together with save/load: what must still work once a game has been loaded.

These tests assume how save/load is called. The assumption lives only in `save` and
`load` below, so whoever implements save/load can adapt those two helpers (or the code)
in one place:

    save(session)  -> the saved game, as plain JSON data
    load(data)     -> a NEW Session that has loaded that data

They are expected to fail until save/load exists.
"""

import json

from game import new_position
from session import Session


def save(session):
    return session.dispatch({"action": "save"})["data"]


def load(data, opponent="human"):
    fresh = Session(opponent)
    fresh.dispatch({"action": "load", "data": data})
    return fresh


def play(session, *moves):
    for source, target in moves:
        session.dispatch({"action": "move", "source": source, "target": target})


def undo(session):
    return session.dispatch({"action": "undo"})


def test_a_loaded_game_is_the_same_game():
    session = Session()
    play(session, ("e2", "e4"), ("e7", "e5"))
    loaded = load(save(session))
    assert loaded.view() == session.view()


def test_moves_made_before_saving_can_be_undone_after_loading():
    session = Session()
    play(session, ("e2", "e4"), ("e7", "e5"), ("g1", "f3"))
    loaded = load(save(session))
    view = undo(loaded)
    assert view["moves"] == ["e2-e4", "e7-e5"]
    assert view["turn"] == "w"
    assert view["board"]["g1"] == "wN" and "f3" not in view["board"]


def test_a_loaded_game_can_be_undone_all_the_way_to_the_start():
    session = Session()
    play(session, ("e2", "e4"), ("e7", "e5"), ("g1", "f3"), ("b8", "c6"))
    loaded = load(save(session))
    for _ in range(4):
        view = undo(loaded)
    assert view["board"] == new_position()[0]
    assert view["turn"] == "w" and view["moves"] == []
    assert view["can_undo"] is False


def test_undoing_a_capture_after_loading_brings_the_piece_back():
    session = Session()
    play(session, ("e2", "e4"), ("d7", "d5"), ("e4", "d5"))
    loaded = load(save(session))
    after_capture = len(loaded.view()["board"])
    view = undo(loaded)
    assert len(view["board"]) == after_capture + 1
    assert view["board"]["d5"] == "bP" and view["board"]["e4"] == "wP"


def test_the_undo_preview_survives_save_and_load():
    session = Session()
    play(session, ("e2", "e4"), ("d7", "d5"), ("e4", "d5"))
    loaded = load(save(session))
    assert loaded.view()["undo_preview"] == session.view()["undo_preview"]
    assert loaded.view()["can_undo"] is True


def test_a_game_saved_after_an_undo_loads_as_it_was_after_the_undo():
    session = Session()
    play(session, ("e2", "e4"), ("e7", "e5"), ("g1", "f3"))
    undo(session)
    loaded = load(save(session))
    assert loaded.view() == session.view()
    assert loaded.view()["moves"] == ["e2-e4", "e7-e5"]


def test_undone_moves_stay_available_for_redo_after_loading():
    session = Session()
    play(session, ("e2", "e4"), ("e7", "e5"), ("g1", "f3"))
    undo(session)
    undo(session)
    loaded = load(save(session))
    assert [entry["label"] for entry in loaded.redo] == ["g1-f3", "e7-e5"]
    assert [entry["label"] for entry in loaded.history] == ["e2-e4"]


def test_a_new_move_after_loading_and_undoing_discards_redo():
    session = Session()
    play(session, ("e2", "e4"), ("e7", "e5"))
    loaded = load(save(session))
    undo(loaded)
    assert len(loaded.redo) == 1
    play(loaded, ("d7", "d5"))
    assert loaded.redo == []
    assert loaded.view()["moves"] == ["e2-e4", "d7-d5"]


def test_the_computer_opponent_is_kept_and_undo_takes_back_both_moves():
    session = Session("computer")
    play(session, ("e2", "e4"))
    session.dispatch({"action": "computer-move"})
    loaded = load(save(session))
    assert loaded.view()["opponent"] == "computer"
    view = undo(loaded)
    assert view["board"] == new_position()[0]
    assert view["turn"] == "w" and view["moves"] == []


def test_loading_replaces_the_current_game_and_its_undo_history():
    saved = Session()
    play(saved, ("e2", "e4"), ("e7", "e5"))
    data = save(saved)
    current = Session()
    play(current, ("d2", "d4"), ("d7", "d5"), ("c2", "c4"))
    current.dispatch({"action": "load", "data": data})
    assert current.view()["moves"] == ["e2-e4", "e7-e5"]
    view = undo(current)
    assert view["moves"] == ["e2-e4"]
    assert "d4" not in view["board"] and view["board"]["d2"] == "wP"


def test_a_saved_game_with_no_moves_has_nothing_to_undo():
    loaded = load(save(Session()))
    view = undo(loaded)
    assert view["board"] == new_position()[0]
    assert view["can_undo"] is False and view["undo_preview"] is None


def test_the_saved_game_survives_a_json_file_round_trip():
    session = Session()
    play(session, ("e2", "e4"), ("e7", "e5"), ("g1", "f3"))
    undo(session)
    data = json.loads(json.dumps(save(session)))
    loaded = load(data)
    assert loaded.view() == session.view()
    assert undo(loaded)["moves"] == ["e2-e4"]


def test_new_game_after_loading_clears_undo_and_redo():
    session = Session()
    play(session, ("e2", "e4"), ("e7", "e5"))
    undo(session)
    loaded = load(save(session))
    loaded.dispatch({"action": "new"})
    assert loaded.history == [] and loaded.redo == []
    assert undo(loaded)["board"] == new_position()[0]


def test_saving_does_not_change_the_game():
    session = Session()
    play(session, ("e2", "e4"), ("e7", "e5"))
    before = session.view()
    save(session)
    assert session.view() == before
    assert len(session.history) == 2
