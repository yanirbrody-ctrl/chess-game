"""Application actions and information shown beside the board."""

from computer import choose_move
from captured import captured_pieces
from game import (
    copy_position,
    legal_moves,
    move,
    new_position,
    promotes,
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

    def play(self, source, target, promotion=None):
        before = copy_position(self.position)
        label = move(self.position, source, target, promotion)
        self.notation.append(label)
        self.history.append({"label": label, "source": source, "target": target,
                             "promotion": promotion,
                             "before": before, "after": copy_position(self.position)})
        self.redo = []
        self.after_move()

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
        return {"captured": captured_pieces(self.history)}

    def dispatch(self, action):
        command = action.get("action")
        if command == "move":
            if self.computer_to_move():
                raise ValueError("Wait for the computer's move")
            self.play(action.get("source"), action.get("target"), action.get("promotion"))
        elif command == "computer-move":
            if not self.computer_to_move():
                raise ValueError("It is not the computer's turn")
            self.play(*choose_move(self.position))
        elif command == "undo":
            self.undo()
        elif command == "legal":
            source = action.get("source")
            targets = legal_moves(self.position, source)
            return {"targets": targets,
                    "promotions": [t for t in targets if promotes(self.position, source, t)]}
        elif command == "new":
            self.__init__(action.get("opponent", "human"))
        elif command == "promotion-setup":
            self.__init__()
            for source, target in PROMOTION_SETUP:
                self.play(source, target)
        else:
            raise ValueError("Unknown action")
        return self.view()
