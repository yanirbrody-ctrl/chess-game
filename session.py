"""Application actions and information shown beside the board."""

import copy
import json

from computer import choose_move
from game import (
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
        # Moves played, oldest first, as {"source", "target"[, "promotion"]}.
        self.history = []
        # Undone moves that redo would replay, next one first.
        self.redo = []

    def play(self, source, target):
        label = move(self.position, source, target)
        self.notation.append(label)
        self.history.append({"source": source, "target": target})
        self.after_move()

    def save(self):
        """Everything needed to rebuild this game, as JSON-ready data."""
        return {
            "format": SAVE_FORMAT,
            "version": SAVE_VERSION,
            "opponent": self.opponent,
            "history": [dict(record) for record in self.history],
            "redo": [dict(record) for record in self.redo],
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
            for record in move_records(saved["history"]):
                session.play(**record)
            current = session.save()
            if any(saved[key] != current[key] for key in ("position", "notation")):
                raise ValueError("the moves do not match the saved board")
            session.redo = move_records(saved["redo"])
            continuation = copy.deepcopy(session)
            for record in session.redo:
                continuation.play(**record)
        # TypeError: a move record whose fields play() does not accept.
        except (ValueError, TypeError) as error:
            raise ValueError(f"Invalid save file: {error}") from None
        return session

    def load(self, text):
        """Replace this game with a saved one, or leave it untouched on error."""
        self.__dict__.update(type(self).from_save(text).__dict__)

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
            self.redo = []
        elif command == "computer-move":
            if not self.computer_to_move():
                raise ValueError("It is not the computer's turn")
            self.play(*choose_move(self.position))
            self.redo = []
        elif command == "save":
            return {"save": self.save()}
        elif command == "load":
            self.load(action.get("data"))
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


def move_records(records):
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
