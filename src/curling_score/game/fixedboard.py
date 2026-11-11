"""Read a wall scoreboard that has a camera of its own at a fixed place in the stream.

Rochester's composite gives the board its own camera, bottom centre, so the
board is not found by its markers (`scoreboard.find_board`): a club's profile
says where it is. It is the same traditional design as Granite's -- a printed
strip of cumulative scores, the end's number on a card hung above it for one
team and below it for the other -- with three differences this module is for:

- the strip runs 1-18, and is followed by a "BLANK ENDS" box;
- a card is a black tile with a white numeral, not a white tile with a dark
  one, on a red band above the strip and a pale one below it;
- the camera looks across the warm room, so people stand in front of it for
  minutes at a time.

What it hands back is `scoreboard.CardBoard`, so everything after the read --
`scoreboard.per_end_from_cards`, the sampler that steps back from the end of
the game (`scoreboard.read_game_board`, through its ``read_at``) -- is
Granite's, unchanged.

People are taken out by the median over a window, as on Granite's board, but a
longer one, and a read is refused unless every slot of both rows is plainly a
card or plainly bare board: someone still in the median is neither. The slots
are found from the strip's own numerals, so nothing is measured by hand but the
rectangle. The numeral is read by Granite's card classifier
(`digits.ConvModel`) from the window's negative; on the first seven Rochester
cards (Go_JOSxJPsQ) it read all seven, six of them at 0.9999 and a 6 at 0.998,
so the bar here is `MIN_CONFIDENCE`, below `scoreboard.MIN_CONFIDENCE`.
"""

from dataclasses import dataclass

import numpy as np

from curling_score.game import scoreboard as sb

# The median's window either side of the moment asked for, and the most
# keyframes held for it. Six minutes cleared the board in eight of nine windows
# of Go_JOSxJPsQ; the ninth is what `_slot_kinds` refuses.
WINDOW_S = 240.0
MAX_FRAMES = 60
MIN_FRAMES = 8
MIN_CONFIDENCE = 0.99

# A numeral's ink on the strip, and a strip row: about a third numeral and the
# rest navy. On Go_JOSxJPsQ the strip's rows are 0.29-0.41 ink and 0.42-0.56
# dark; the red band above is under 0.06 ink, the pale one below over 0.85.
# Sheet C's camera is closer and its numerals bolder: 0.45-0.52 ink.
_INK_LEVEL = 170
_STRIP_DARK_LEVEL = 110
_STRIP_MIN_DARK = 0.30
_STRIP_INK = (0.20, 0.60)
_STRIP_MIN_ROWS = 12
# The widest gap between two digits of one numeral, in pixels, and how far a
# numeral may sit off the even spacing, in slots.
_DIGIT_GAP = 7
_MAX_SLOT_OFF = 0.25
# The card rows, in strip heights above the strip's top and below its bottom.
_TOP_ROW = (1.10, 0.04)
_BOTTOM_ROW = (0.25, 1.45)
# How much of a card row may run off the picture, in strip heights, and be
# read from what is left: sheet C's board camera frames the board's top edge
# a row or two above the cards.
_ROW_OFF_PICTURE = 0.15
# A slot's window, in pitches either side of its centre.
_HALF_WINDOW = 0.42
# A window that is a card (black), and the least of it that must be one thing
# or the other for the slot to be called.
_CARD_V = 80
_CARD_MIN = 0.35
_BARE_MIN = 0.60


@dataclass(frozen=True)
class FixedBoard:
    """Where a club's board camera sits in the composite, and how to read it.

    ``rect`` is (x, y, w, h) in the full frame. ``strip_x`` is the part of its
    width the printed numerals occupy, as fractions -- past the word SCORE and
    short of the BLANK ENDS box. ``top`` and ``bottom`` are the teams whose
    cards hang above and below the strip. ``card_v`` is the brightness under
    which a pixel is a card's: a softer camera blurs the black tiles grey
    (V 75-115 on sheet B, against the red band's 100 and up only at its edges).
    ``top_row`` is where the top team's cards hang, in strip heights above the
    strip's top (`_TOP_ROW`): on sheet C they hang over its top edge.
    """

    rect: tuple
    slots: int = 18
    strip_x: tuple = (0.125, 0.90)
    top: str = "red"
    bottom: str = "yellow"
    card_v: int = _CARD_V
    top_row: tuple = _TOP_ROW


class Unreadable(Exception):
    """This image of the board cannot be read; why is the message."""


def _runs(flags):
    out, start = [], None
    for i, on in enumerate(flags):
        if on and start is None:
            start = i
        elif not on and start is not None:
            out.append((start, i))
            start = None
    if start is not None:
        out.append((start, len(flags)))
    return out


def strip_rows(gray, board: FixedBoard):
    """(top, bottom) rows of the printed strip: the band of navy with numerals on it."""
    x0, x1 = (int(f * gray.shape[1]) for f in board.strip_x)
    band = gray[:, x0:x1]
    dark = (band < _STRIP_DARK_LEVEL).mean(axis=1)
    ink = (band > _INK_LEVEL).mean(axis=1)
    rows = (dark >= _STRIP_MIN_DARK) & (ink >= _STRIP_INK[0]) & (ink <= _STRIP_INK[1])
    runs = [r for r in _runs(rows) if r[1] - r[0] >= _STRIP_MIN_ROWS]
    if not runs:
        raise Unreadable("no printed strip")
    return max(runs, key=lambda r: r[1] - r[0])


def slot_centres(gray, board: FixedBoard, rows):
    """Each slot's centre column, from the strip's first numeral and its last.

    The numerals are evenly spaced, so the first ("1") and the last ("18")
    give them all. Glyphs are grouped into numerals by the gap between them:
    a softer camera runs the two digits of "10" into one glyph (sheets B and
    D), a sharp one keeps them apart by 5 px or less, and numerals stand
    10 px or more apart. A strip with a different number of numerals than
    1-``slots``, or numerals off the even spacing, has something in front of it.
    """
    y0, y1 = rows
    x0, x1 = (int(f * gray.shape[1]) for f in board.strip_x)
    cols = (gray[y0:y1, x0:x1] > _INK_LEVEL).sum(axis=0) >= 3
    runs = [(a + x0, b + x0) for a, b in _runs(cols) if b - a >= 2]
    numerals = []
    for a, b in runs:
        if numerals and a - numerals[-1][1] <= _DIGIT_GAP:
            numerals[-1] = (numerals[-1][0], b)
        else:
            numerals.append((a, b))
    if len(numerals) != board.slots:
        raise Unreadable(f"the strip shows {len(numerals)} numerals, not {board.slots}")
    centres = [(a + b) / 2 for a, b in numerals]
    first, last = centres[0], centres[-1]
    pitch = (last - first) / (board.slots - 1)
    xs = [first + i * pitch for i in range(board.slots)]
    off = max(abs(c - x) for c, x in zip(centres, xs))
    if off > _MAX_SLOT_OFF * pitch:
        raise Unreadable(f"a numeral sits {off / pitch:.2f} of a slot off the strip's spacing")
    return xs, pitch


def _bare(hsv_window, row: str):
    """How much of a window is the board with nothing hung on it: the red
    band above the strip, the pale one below."""
    h, s, v = hsv_window[..., 0], hsv_window[..., 1], hsv_window[..., 2]
    if row == "top":
        return float((((h <= 10) | (h >= 168)) & (s >= 90) & (v >= 90)).mean())
    return float(((v >= 150) & (s <= 70)).mean())


def read_image(image, board: FixedBoard, *, predict=None) -> sb.CardBoard:
    """The cards on one de-occluded image of the board camera's rectangle.

    Raises `Unreadable` when the strip is not all there or any slot is neither
    a card nor bare board. ``predict`` is the numeral classifier's, for tests.
    """
    import cv2

    image = np.asarray(image)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    rows = strip_rows(gray, board)
    xs, pitch = slot_centres(gray, board, rows)
    height = rows[1] - rows[0]
    half = max(2, int(pitch * _HALF_WINDOW))
    bands = {"top": (rows[0] - board.top_row[0] * height, rows[0] - board.top_row[1] * height),
             "bottom": (rows[1] + _BOTTOM_ROW[0] * height, rows[1] + _BOTTOM_ROW[1] * height)}
    if predict is None:
        from curling_score.game import digits

        predict = digits.load_default_model().predict
    out = {}
    for row, team in (("top", board.top), ("bottom", board.bottom)):
        y0, y1 = (int(round(v)) for v in bands[row])
        slack = _ROW_OFF_PICTURE * height
        if y0 < -slack or y1 > gray.shape[0] + slack:
            raise Unreadable(f"the {row} row runs off the picture")
        y0, y1 = max(0, y0), min(gray.shape[0], y1)
        cards = []
        for slot, x in enumerate(xs, 1):
            xa, xb = int(x) - half, int(x) + half
            window = hsv[y0:y1, xa:xb]
            card = float((window[..., 2] < board.card_v).mean())
            if card < _CARD_MIN:
                if _bare(window, row) < _BARE_MIN:
                    raise Unreadable(f"something is in front of the {row} row at {slot}")
                continue
            # Granite's cards are dark ink on a white tile: this one's negative.
            glyph = sb.glyph_in_window(255 - gray[y0:y1, xa:xb])
            end, confidence = predict(glyph) if glyph is not None else (None, 0.0)
            cards.append(sb.Card(slot=slot, end=end if confidence >= MIN_CONFIDENCE else None,
                                 confidence=float(confidence)))
        out[team] = tuple(cards)
    return sb.CardBoard(yellow=out.get("yellow", ()), red=out.get("red", ()))


def crop(frame, board: FixedBoard):
    x, y, w, h = board.rect
    return np.asarray(frame)[y:y + h, x:x + w]


def read_cards_at(video_path, t_seconds, board: FixedBoard, *, window_s: float = WINDOW_S,
                  max_frames: int = MAX_FRAMES):
    """The cards around a moment in the video, or None when the board cannot
    be read there (`scoreboard.read_cards_at`, for a board at a fixed place).
    Only the board's rectangle of each keyframe is kept."""
    from curling_score.ingest import frames as F

    lo, hi = max(0.0, t_seconds - window_s), t_seconds + window_s
    imgs = []
    for t, img in F.keyframe_sweep(video_path, start_s=lo, end_s=hi):
        if t < lo:
            continue
        imgs.append(np.ascontiguousarray(crop(img, board)))
    if len(imgs) < MIN_FRAMES:
        return None
    if len(imgs) > max_frames:
        imgs = [imgs[i * len(imgs) // max_frames] for i in range(max_frames)]
    try:
        return read_image(np.median(np.stack(imgs), axis=0).astype(np.uint8), board)
    except Unreadable:
        return None


def reader(video_path, board: FixedBoard):
    """``read_at`` for `scoreboard.read_game_board`."""
    return lambda t: read_cards_at(video_path, t, board)
