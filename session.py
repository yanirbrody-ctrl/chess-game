"""Application actions and information shown beside the board."""

import copy
import json

from computer import choose_move
from game import (
    copy_position,
    legal_moves,
    move,
    new_position,
    status,
    winner,
)


# Legal from the standard starting position under this game's rules.
# Next move: b7-a8, capturing a rook and reaching the last rank.
PROMOTION_SETUP = [
    ("a2", "a4"), ("h7", "h5"),
    ("a4", "a5"), ("h5", "h4"),
    ("a5", "a6"), ("h4", "h3"),
    ("a6", "b7"), ("h3", "g2"),
]

SAVE_FORMAT = "aicode-chess-save"
SAVE_VERSION = 1
SAVE_FIELDS = {"opponent", "history", "redo", "position", "notation"}
MOVE_FIELDS = {"source", "target", "promotion"}


class Session:
    def __init__(self, opponent="human"):
        if opponent not in ("human", "computer"):
            raise ValueError("Unknown opponent")
        self.position = new_position()
        self.notation = []
        self.opponent = opponent
        # One entry per move played, oldest first. Each entry is plain JSON data:
        #   {"label": "e2-e4", "before": [board, turn], "after": [board, turn]}
        # `history` holds the moves currently played; `redo` holds undone moves, with the
        # most recently undone move last. A new move discards `redo`.
        self.history = []
        self.redo = []

    def play(self, source, target):
        before = copy_position(self.position)
        label = move(self.position, source, target)
        self.notation.append(label)
        self.history.append({"label": label, "source": source, "target": target,
                             "before": before, "after": copy_position(self.position)})
        self.redo = []
        self.after_move()

    def save(self):
        """Everything needed to rebuild this game, as JSON-ready data."""
        return {
            "format": SAVE_FORMAT,
            "version": SAVE_VERSION,
            "opponent": self.opponent,
            "history": [move_record(entry) for entry in self.history],
            # The file lists redo in replay order: the next move to redo first.
            "redo": [move_record(entry) for entry in reversed(self.redo)],
            "position": {"board": dict(self.position[0]), "turn": self.position[1]},
            "notation": list(self.notation),
        }

    @classmethod
    def from_save(cls, text):
        """Rebuild a game from save-file text by replaying its moves.

        The saved board, turn and notation must match the replay, and the redo moves
        must be playable after it. Anything else raises ValueError starting
        "Invalid save file".
        """
        try:
            saved = parse_save(text)
            session = cls(saved["opponent"])
            for record in parse_moves(saved["history"]):
                session.play(**record)
            current = session.save()
            if any(saved[key] != current[key] for key in ("position", "notation")):
                raise ValueError("the moves do not match the saved board")
            # Replaying the redo moves checks them and builds their full entries.
            continuation = copy.deepcopy(session)
            for record in parse_moves(saved["redo"]):
                continuation.play(**record)
            session.redo = continuation.history[len(session.history):][::-1]
        # TypeError: a move record whose fields play() does not accept.
        except (ValueError, TypeError) as error:
            raise ValueError(f"Invalid save file: {error}") from None
        return session

    def load(self, text):
        """Replace this game with a saved one, or leave it untouched on error."""
        self.__dict__.update(type(self).from_save(text).__dict__)

    def undo(self):
        """Take back the last move. Against the computer, take back its reply as well,
        so it is the player's turn again. Does nothing when there is no move."""
        for _ in range(self.undo_count()):
            self.take_back()

    def undo_count(self):
        """How many moves undo takes back: 0 with no history, 2 when it also takes back
        the computer's reply to the player's move, otherwise 1."""
        if not self.history:
            return 0
        if (self.opponent == "computer" and len(self.history) >= 2
                and self.history[-1]["before"][1] == "b"):
            return 2
        return 1

    def undo_preview(self):
        """The moves undo would take back, latest first, or None. The page draws them
        as a ghost: `piece` goes back to `source`, and `captured` returns to `target`."""
        count = self.undo_count()
        if not count:
            return None
        return {"moves": [
            {"label": entry["label"], "source": entry["source"], "target": entry["target"],
             "piece": entry["before"][0][entry["source"]],
             "captured": entry["before"][0].get(entry["target"])}
            for entry in reversed(self.history[-count:])]}

    def take_back(self):
        entry = self.history.pop()
        self.position = copy_position(entry["before"])
        self.notation.pop()
        self.redo.append(entry)

    def after_move(self):
        pass

    def view(self):
        return {
            "board": self.position[0],
            "turn": self.position[1],
            "moves": self.notation,
            "opponent": self.opponent,
            "status": status(self.position),
            "winner": winner(self.position),
            "can_undo": bool(self.history),
            "undo_preview": self.undo_preview(),
            **self.sidebar(),
        }

    def computer_to_move(self):
        return (self.opponent == "computer" and self.position[1] == "b"
                and status(self.position) not in ("checkmate", "stalemate"))

    def sidebar(self):
        return {}

    def dispatch(self, action):
        command = action.get("action")
        if command == "move":
            if self.computer_to_move():
                raise ValueError("Wait for the computer's move")
            self.play(action.get("source"), action.get("target"))
        elif command == "computer-move":
            if not self.computer_to_move():
                raise ValueError("It is not the computer's turn")
            self.play(*choose_move(self.position))
        elif command == "save":
            return {"save": self.save()}
        elif command == "load":
            self.load(action.get("data"))
        elif command == "undo":
            self.undo()
        elif command == "legal":
            return {"targets": legal_moves(self.position, action.get("source"))}
        elif command == "new":
            self.__init__(action.get("opponent", "human"))
        elif command == "promotion-setup":
            self.__init__()
            for source, target in PROMOTION_SETUP:
                self.play(source, target)
        else:
            raise ValueError("Unknown action")
        return self.view()


def parse_save(text):
    """Decode save-file text into a dict with every field of the current format."""
    if not isinstance(text, str):
        raise ValueError("expected the file's text")
    try:
        saved = json.loads(text)
    except json.JSONDecodeError:
        raise ValueError("not JSON") from None
    if not isinstance(saved, dict) or saved.get("format") != SAVE_FORMAT:
        raise ValueError("not a chess save")
    if saved.get("version") != SAVE_VERSION:
        raise ValueError("unsupported version")
    missing = SAVE_FIELDS - set(saved)
    if missing:
        raise ValueError("missing " + ", ".join(sorted(missing)))
    return saved


def move_record(entry):
    """The part of a history entry that a save file keeps."""
    return {key: entry[key] for key in MOVE_FIELDS if key in entry}


def parse_moves(records):
    """Validate a saved list of move records and return copies of them."""
    if not isinstance(records, list):
        raise ValueError("moves must be a list")
    result = []
    for record in records:
        if (not isinstance(record, dict) or not {"source", "target"} <= set(record)
                or not set(record) <= MOVE_FIELDS):
            raise ValueError("each move needs a source and a target")
        result.append(dict(record))
    return result
