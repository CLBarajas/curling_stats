"""Guards the overhead cannot see, placed from the long camera behind the thrower.

DFW's overheads show the house and about 3.5 m in front of the tee: a guard
resting between there and the hog line is in no panel, and the overhead's
house state has no stone for it. The long camera at the throwing end looks
down the sheet at that ice. At each rock's rest, the stones it shows in that
band are mapped onto the house (`SideView.to_house`, read at the stone's
footprint: its near edge, toward the camera, one radius from its centre) and
added to that rock's stones as ``"source": "long"`` -- an estimate, the camera
seeing that ice at a shallow angle (roughly +/-0.2-0.4 m). A stone already
in the overhead's state (within DEDUPE_M) is not added twice. Each rock's
state is read at its own rest, so a guard stays until it is hit or the end is
over. A rock the overhead could not place (no ``delivered_stone_index``) is
marked as the long stone of its colour that its own rest brought -- and one the
far house never saw arrive, timed across the far hog line, is read once it has
had time to stop there (`_read_at`) and, found, is a guard. A rock the
overhead saw touch nothing, after which a guard is gone for good, struck that
guard out front (`struck_out_front`).
"""

import math
from statistics import median

from curling_score.geometry import constants as C

# Within this of a stone the state has already, a long stone is that stone.
DEDUPE_M = 0.45
# ...but two stones of one colour seen apart in the same read (`standing`)
# are two, unless closer than two stones can stand: a guard thrown beside
# another. Rochester sheet B 10/28 (6IUB9KbPkpc) end 5 rock 5 stopped 0.32 m
# from rock 1's guard and end 8 rock 4 0.37 m from rock 2's, both read apart,
# and each was dropped as the other, so neither rock had a place.
SAME_READ_M = 2 * C.STONE_RADIUS_M
# A rock the far house saw do nothing that left a guard gone from the next two
# reads struck it: a takeout out front, which the house-only overhead cannot
# see (sheet B 10/28 end 1 rock 10, a peel of a centre guard; end 8 rock 9,
# a peel that took the high guard). Only these, which say nothing was hit.
STRUCK_OUT_FRONT = ("flashed", "unknown")
# Past the hog line, a stone is out of play.
MAX_Y_M = C.TEE_TO_HOGLINE_M + C.STONE_RADIUS_M
# Read this long after a rock's rest: the stone has stopped, sweepers moving off.
AFTER_REST_S = 0.5
# A rock the far house never saw arrive has no rest of its own -- it "rests"
# MIN_LAG_S after its release, still sliding mid-sheet. Timed across the far
# hog line, it is read this long after that crossing instead: DFW's guards
# stop 3-5 s past the line (46wEMds_tYQ end 3 rock 1: crossed at +19.0 s,
# still from +23.5 s). Never later than just before the next rock is thrown.
AFTER_FAR_S = 6.0
BEFORE_NEXT_S = 1.0
# What a rock nothing else could name becomes when the guard it left is found.
NAMEABLE = ("unknown", "hogged")


def _read_at(shot, next_shot, after_far_s: float = AFTER_FAR_S) -> float:
    """When to read the stones a rock left: just after its rest, or for one with
    no arrival but a far hog crossing, once it has had time to stop past it.
    ``after_far_s`` is that time where a club's guards take longer than DFW's
    (`clubs.Club.guards_after_far_s`)."""
    t = shot["t_rest_s"] + AFTER_REST_S
    if shot.get("delivered_stone_index") is None and shot.get("t_far_s") is not None:
        t = max(t, shot["t_far_s"] + after_far_s)
        nxt = (next_shot or {}).get("t_release_s")
        if nxt is not None:
            t = min(t, nxt - BEFORE_NEXT_S)
    return t


def place(stones, view, known, from_m: float) -> list[dict]:
    """``stones`` -- ``(edge_row, cx, color)`` in view pixels -- as timeline
    stones, for those resting between ``from_m`` in front of the tee and the
    hog line, on the sheet, and not already ``known`` (house dicts)."""
    out = []
    for row, cx, color in stones:
        x, y_edge = view.to_house(cx, row)
        y = y_edge - C.STONE_RADIUS_M
        if not (from_m <= y <= MAX_Y_M) or abs(x) > C.SIDELINE_ABS_X_M:
            continue
        if any(math.hypot(x - k["x"], y - k["y"]) < DEDUPE_M for k in known):
            continue
        if any(math.hypot(x - g["x"], y - g["y"]) < (SAME_READ_M if g["color"] == color else DEDUPE_M)
               for g in out):
            continue
        x, y = round(x, 4), round(y, 4)
        out.append({"color": color, "x": x, "y": y,
                    "distance_to_tee": math.hypot(x, y), "in_house": False,
                    "confidence": None, "source": "long"})
    return out


def unmatched(a, b, within: float = DEDUPE_M):
    """The stones of ``a`` and of ``b`` that are not the same stone as one in
    the other: pairs of one colour within ``within``, nearest first, each stone
    in one pair at most. Two guards side by side are two stones, not one seen
    twice, so a stone already paired cannot vouch for a second."""
    pairs = sorted((math.hypot(p["x"] - q["x"], p["y"] - q["y"]), i, j)
                   for i, p in enumerate(a) for j, q in enumerate(b) if p["color"] == q["color"])
    used_a, used_b = set(), set()
    for dist, i, j in pairs:
        if dist >= within:
            break
        if i not in used_a and j not in used_b:
            used_a.add(i)
            used_b.add(j)
    return ([p for i, p in enumerate(a) if i not in used_a],
            [q for j, q in enumerate(b) if j not in used_b])


def add(end: dict, view, read_stones, from_m: float, after_far_s: float = AFTER_FAR_S) -> int:
    """Add the long camera's guards to each rock of a built ``end`` (and its
    final stones). ``read_stones(t)`` gives the ``(edge_row, cx, color)`` of
    the stones the view shows at ``t``. Returns how many long stones it added
    in all."""
    n, last = 0, []
    shots = end.get("shots") or []
    for i, shot in enumerate(shots):
        if shot.get("missing") or shot.get("t_rest_s") is None:
            continue
        stones = shot.setdefault("stones", [])
        nxt = next((s for s in shots[i + 1:] if not s.get("missing")), None)
        extra = place(read_stones(_read_at(shot, nxt, after_far_s)), view, stones, from_m)
        if shot.get("delivered_stone_index") is None:
            new = [g for g in unmatched(last, extra)[1] if g["color"] == shot.get("color")]
            if len(new) == 1:
                shot["delivered_stone_index"] = len(stones) + extra.index(new[0])
                if shot.get("shot_type") in NAMEABLE and shot.get("t_far_s") is not None:
                    shot["shot_type"] = "guard"
        stones.extend(extra)
        # An empty overhead reading of a rock that came to rest marks its house
        # unread (`shots.from_deliveries`): the stone has to be somewhere. Found
        # here, it is somewhere, and the viewer can chart the rock.
        if shot.get("state_known") is False and shot.get("delivered_stone_index") is not None:
            shot["state_known"] = True
        n += len(extra)
        last = extra
    if last and end.get("final_stones") is not None:
        end["final_stones"].extend(dict(g) for g in last)
    struck_out_front(shots)
    return n


def struck_out_front(shots) -> int:
    """Name a hit each rock in STRUCK_OUT_FRONT after which a guard the end
    camera read is gone, and stays gone at the next rock's read: the guard
    goes into the rock's ``house_delta`` as removed. Returns how many."""
    from curling_score.game.classify import CONF_HOUSE_CHANGED

    read = [i for i, s in enumerate(shots)
            if not s.get("missing") and s.get("t_rest_s") is not None]
    longs = {i: [g for g in shots[i].get("stones") or [] if g.get("source") == "long"] for i in read}
    hits = 0
    for k, i in enumerate(read[1:], 1):
        shot = shots[i]
        if shot.get("shot_type") not in STRUCK_OUT_FRONT:
            continue
        gone = unmatched(longs[read[k - 1]], longs[i])[0]
        if k + 1 < len(read):
            gone = unmatched(gone, longs[read[k + 1]])[0]
        if not gone:
            continue
        delta = dict(shot.get("house_delta") or {"added": [], "removed": [], "moved": []})
        delta["removed"] = list(delta.get("removed") or []) + [dict(g) for g in gone]
        shot["house_delta"] = delta
        shot["shot_type"], shot["shot_type_confidence"] = "hit", CONF_HOUSE_CHANGED
        hits += 1
    return hits


READ_S, READ_FPS = 0.6, 10.0

# `sidemodel.propose` files a colour's detections by 120 px column, one track
# a column: right for the one stone a throw moves, but two standing stones can
# share a column, and the median of both is neither. Rochester sheet B 10/28
# (6IUB9KbPkpc) end 1: a blue centre guard at +2.10 m and rock 5 at +0.81 m
# read as one stone at +1.42 m, inside `from_m`, and the guard went missing
# from the house until rock 5 was gone; likewise red 6's guard behind red 8.
# A column's detections are split into stones first: one stone's boxes stay
# within these shares of its width of each other, across and along the sheet
# (a stone frozen behind another sits about 0.28 of a width further up, on
# sheet B's left camera at +2 m).
SAME_STONE_COL = 0.5
SAME_STONE_ROW = 0.2


def standing(track):
    """``track``'s ``(t, edge_row, body_px, cx)`` detections as the stones
    standing in its column: lists of the detections of one stone each."""
    stones = []
    for p in sorted(track, key=lambda p: (p[1], p[-1])):
        _t, row, body, *_rest = p
        cx = p[-1]
        for s in stones:
            if (abs(row - median([q[1] for q in s])) < SAME_STONE_ROW * body
                    and abs(cx - median([q[-1] for q in s])) < SAME_STONE_COL * body):
                s.append(p)
                break
        else:
            stones.append([p])
    return stones


def stones_reader(video, view, *, model=None, decode=None, propose=None):
    """``read_stones(t)`` for `add`: the stones of both colours the side model
    finds in ``view`` over READ_S from ``t``, each the median
    ``(edge_row, cx, color)`` of one stone's detections (`standing`) -- they
    are standing still."""
    import numpy as np

    from curling_score.detect import longview, sidemodel

    model = model or sidemodel.default_model()
    decode = decode or longview.decode
    propose = propose or sidemodel.propose

    def read(t):
        if model is None:
            return []
        frames, times = decode(video, view.rect, t, t + READ_S, READ_FPS)
        if not len(frames):
            return []
        out = []
        for color in ("red", "yellow"):
            for track in propose(model, frames, view, color, times).values():
                for stone in standing(track):
                    if len(stone) >= 2:
                        out.append((float(np.median([r for _t, r, *_ in stone])),
                                    float(np.median([c for *_x, c in stone])), color))
        return out
    return read
