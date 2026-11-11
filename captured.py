"""The captured-pieces sidebar, worked out from the moves played."""


def captured_pieces(history):
    """Pieces actually captured, oldest first, each with the type it had when captured.

    `history` is Session.history. A move captures when its target square was occupied
    on the board before the move, so undoing a move (which removes its history entry)
    removes its capture too, and a pawn that promoted is never counted as captured.
    """
    return [entry["before"][0][entry["target"]]
            for entry in history if entry["target"] in entry["before"][0]]
