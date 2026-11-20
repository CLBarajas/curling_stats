"""Releases the overhead panel lost, timed from the long camera facing the thrower.

The overhead release (``detect/release.py``) is the stone seen leaving the hack
and crossing a line a foot behind the tee. A thrower who slides with head and
shoulders over the stone hides it from above: the panel sees it for the first
metre out of the hack and loses it 0.4-0.9 m short of that line. The misses
cluster on a player -- on 2026-09-27, 10 of one lead's 12 rocks -- and they cost
each rock its release time and speed, its aim line, and a real tee crossing for
the thinking clock and the broom read.

The camera at the other end (``hogtime.CAMERA_FOR[OTHER_HOUSE[house]]``, the
one that already times the throwing hog line) looks up the sheet at the
delivery, with the stone running in front of the thrower. Its slide past the
hack is near-constant speed, so a straight line through the early samples
times it at any point. Measured on three games (``~/curling-work/release-spike``):
it timed every rock the overhead timed (83/83, 89/89, 110/110) to a median
absolute deviation of 0.05-0.12 s, and 33 of the overhead's 36 misses.

Its instant is not the overhead's: the overhead times a stone's first
sighting, and a long camera can run out of step with the panel -- by -0.11 to
+0.23 s between those games, and by 0.45 s for part of one. So each end
calibrates itself: rocks both saw give the correction the filled ones get.

Fill-in only, and attach-only like ``hogtime``, ``broomtime`` and ``linetime``:
it gives a release to a shot that has none, never replaces the overhead's, and
cannot add, drop or renumber a shot. An end with nothing to fill reads no video.

One case filling in cannot reach: a rock the overhead saw at *neither* end. A
hogged rock never comes into the far house, so its release is all the evidence
it leaves, and when the thrower hides that too there is no shot to fill in.
PHbZ3EKOhMI end 6 opened with exactly that -- the red lead whose releases the
overhead lost all game hogged rock 1 at 5341 -- and with fifteen rocks seen the
missing one was placed last, which gave red the hammer and named every red
thrower one rock early. ``lost_rocks`` looks for such throws, and only in an
end the rules leave short: it scans this same camera where a rock could hide
and hands back every slide that no release and no arrival accounts for, as the
releases ``detect.release`` settles like any other.
"""
from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass

import numpy as np

from curling_score.detect import release as R
from curling_score.fpframes import record as fp_record
from curling_score.game import hogtime, split, thinking
from curling_score.geometry import constants as C

log = logging.getLogger(__name__)

# Where the slide is timed: 2 m behind the throwing tee, about where the
# overhead panel first sees a stone leave the hack.
REF_Y_M = -2.0
# The early slide only: from behind the house to a few metres past the tee,
# before sweeping and curl. Past the tee the thrower is often up and the
# sweepers alongside.
FIT_Y_M = (-3.0, 3.0)
FIT_TOL_M = 0.25
FIT_MIN_N = 4
FIT_MIN_SPAN_M = 1.0
# A delivery's slide. Good fits in the spike ran 0.83-2.55 m/s; a stone parked
# in front of the hack, or nudged into place, is far slower.
SPEED_M_S = (0.8, 4.5)
# Off the centre line is not the delivery: the next rock parked beside the
# hack, a stone kicked to the side.
X_MAX_M = 0.6
# Read from 6 s before the hog crossing (the slide takes 3-4 s from the hack)
# to just after it. With no crossing, from the arrival: the widest release-to-
# arrival lag the overhead measures, to the shortest.
WINDOW_FROM_HOG_S = (-6.0, 0.5)
FPS = 10.0
# Rocks the end calibrates against: the overhead releases with the longest
# tracks, since those are the surest first sightings. Fewer than CALIB_MIN,
# and no correction at all -- the three games spread either side of zero.
CALIB_N = 4
CALIB_MIN = 2
SOURCE = "side"


@dataclass(frozen=True)
class Slide:
    """The stone's slide past the hack, as the long camera saw it."""

    t_ref: float        # when it crossed REF_Y_M
    t_tee: float        # when it crossed the tee
    speed_m_s: float
    n: int
    span_m: float
    x_m: float
    y_max_m: float
    # The longest wait between two of its samples: a stone that slides is seen
    # frame after frame, while a "slide" drawn through stones at rest is seen
    # only where the line crosses each one.
    max_gap_s: float = 0.0

    def t_at(self, y: float) -> float:
        return self.t_ref + (y - REF_Y_M) / self.speed_m_s


def fit_slide(points) -> Slide | None:
    """A straight y(t) through the slide in ``points`` -- (t, y, x), y past the
    throwing tee -- or None when they hold no slide.

    The line through the most samples within ``FIT_TOL_M`` of it, chosen from
    every pair; then one sample a frame, and a refit on those. A stone parked in
    front of the hack, and stray boxes, sit off any line a slide makes.
    """
    lo, hi = FIT_Y_M
    p = [(float(t), float(y), float(x)) for t, y, x in points if lo <= y <= hi]
    if len(p) < FIT_MIN_N:
        return None
    best = None
    for i in range(len(p)):
        for j in range(i + 1, len(p)):
            (t1, y1, _), (t2, y2, _) = p[i], p[j]
            if t2 == t1:
                continue
            v = (y2 - y1) / (t2 - t1)
            if not SPEED_M_S[0] <= v <= SPEED_M_S[1]:
                continue
            inl = [q for q in p if abs(q[1] - (y1 + v * (q[0] - t1))) <= FIT_TOL_M]
            if len({q[0] for q in inl}) >= FIT_MIN_N and (best is None or len(inl) > len(best)):
                best = inl
    if best is None:
        return None
    b, c = np.polyfit([q[0] for q in best], [q[1] for q in best], 1)
    frame = {}
    for q in best:
        r = abs(q[1] - (b * q[0] + c))
        if q[0] not in frame or r < frame[q[0]][0]:
            frame[q[0]] = (r, q)
    kept = [frame[t][1] for t in sorted(frame)]
    ts = np.array([q[0] for q in kept]); ys = np.array([q[1] for q in kept])
    if len(kept) < FIT_MIN_N or np.ptp(ys) < FIT_MIN_SPAN_M:
        return None
    b, c = np.polyfit(ts, ys, 1)
    if not SPEED_M_S[0] <= b <= SPEED_M_S[1]:
        return None
    t_ref = float((REF_Y_M - c) / b)
    return Slide(t_ref=t_ref, t_tee=float(-c / b), speed_m_s=float(b), n=len(kept),
                 span_m=float(np.ptp(ys)), x_m=float(np.median([q[2] for q in kept])),
                 y_max_m=float(ys.max()),
                 max_gap_s=float(np.diff(ts).max()) if len(ts) > 1 else 0.0)


def stone_points(view, times, per_frame) -> list:
    """The side model's boxes -- per frame, (cx, bottom_row, width, conf) in the
    view's rows -- as (t, y past the throwing tee, x) on the centre line.

    The same mapping ``linetime`` uses: a box's bottom edge is the stone's near
    side, one radius short of its centre, and the camera faces the thrower, so
    its image-left is the thrower's right.
    """
    rec = fp_record.active()
    out = []
    for t, boxes in zip(times, per_frame):
        for cx, row, w, conf in boxes:
            if rec is not None:
                rec.side_box(view, t, cx, row, w, conf, color=None, pass_="slide")
            y = view.metres_at(row) - C.STONE_RADIUS_M
            x = -view.lateral_x(cx, view.row_for(y))
            if abs(x) <= X_MAX_M:
                out.append((float(t), float(y), float(x)))
    return out


def side_points(video, view, color, t0, t1, *, model=None, decode=None, detect=None):
    """What the long camera saw of ``color`` from 1 m behind the hack to below
    the hog line, over ``t0..t1``."""
    if decode is None:
        from curling_score.detect import longview
        decode = longview.decode
    if detect is None:
        from curling_score.detect import sidemodel
        detect = sidemodel.detect_band
    if model is None:
        from curling_score.detect import sidemodel
        model = sidemodel.default_model()
    frames, times = decode(video, view.rect, t0, t1, FPS)
    if not len(frames):
        return []
    top, bot = _band(view)
    return stone_points(view, times, detect(model, frames, times, top, bot, color))


def _band(view):
    """The view's rows from 1 m behind the hack to just below the hog line."""
    top = max(0, int(view.row_for(-(C.TEE_TO_HACKLINE_M + 1.0))) - 30)
    return top, int(view.hog_row) + 40


def _window(shot):
    t_hog = getattr(shot, "t_hog_s", None)
    if t_hog is not None:
        return t_hog + WINDOW_FROM_HOG_S[0], t_hog + WINDOW_FROM_HOG_S[1]
    delivery = getattr(shot, "delivery", None)
    if delivery is None:
        return None
    return delivery.t_enter - R.MAX_LAG_S, delivery.t_enter - R.MIN_LAG_S


def _slide_for(shot, video, view, points):
    w = _window(shot)
    if w is None:
        return None
    return fit_slide(points(video, view, shot.color, *w))


def _planned_windows(shots, view) -> list:
    """The windows `time_side_releases` will decode for ``shots``, in order, as
    `longview.Plan` takes them. A rock whose window cannot be worked out is
    left out, and decoded (or refused) when the pass reaches it: the plan only
    reads ahead."""
    out = []
    for s in shots:
        try:
            w = _window(s)
        except Exception:  # noqa: BLE001
            continue
        if w is not None:
            out.append((view.rect, *w, FPS))
    return out


def time_side_releases(shots, video, view, *, points=None) -> int:
    """Give each shot the overhead lost a release from the long camera, in
    place; return how many it gave one.

    ``view`` is the camera that sees the thrower's house -- hogtime's. A no-op
    without lateral calibration, which the centre-line test needs. ``points``
    is ``(video, view, color, t0, t1) -> [(t, y, x)]``, the side model by
    default. A decode or detector error costs that rock its release, not the
    end its analysis.
    """
    if view is None or not getattr(view, "has_lateral", False):
        return 0
    todo = [s for s in shots if not getattr(s, "missing", False)
            and getattr(s, "release", None) is None]
    if not todo:
        return 0
    # The end's own correction, from the overhead releases with the most samples.
    known = sorted((s for s in shots if not getattr(s, "missing", False)
                    and getattr(s, "release", None) is not None
                    and getattr(s.release, "source", "overhead") != SOURCE),
                   key=lambda s: -len(getattr(s.release, "track", ())))[:CALIB_N]
    if points is None:
        from curling_score.detect import longview

        # Each rock's window decodes while the one before it is read, in the
        # order they are read below: the calibration's rocks, then the rest. A
        # window hangs off its rock's hog crossing or arrival, neither of
        # which this pass touches.
        plan = longview.Plan(video, _planned_windows(known + todo, view))

        def points(video, view, color, t0, t1):
            return side_points(video, view, color, t0, t1, decode=plan.decode)

    def seen(shot):
        try:
            return _slide_for(shot, video, view, points)
        except Exception:
            log.exception("long-camera release failed on shot %s; it keeps none",
                          getattr(shot, "number", "?"))
            return None

    d_rel, d_tee = [], []
    for s in known:
        got = seen(s)
        if got is None:
            continue
        d_rel.append(s.release.t - got.t_ref)
        tee = split.crossing_time(getattr(s.release, "track", ()), thinking.TEE_LINE_Y_M)
        if tee is not None:
            d_tee.append(tee - got.t_tee)
    off_rel = statistics.median(d_rel) if len(d_rel) >= CALIB_MIN else 0.0
    off_tee = statistics.median(d_tee) if len(d_tee) >= CALIB_MIN else 0.0

    n = 0
    for s in todo:
        got = seen(s)
        if got is None:
            continue
        s.release = _as_release(s.color, got, off_rel, off_tee)
        s.tee_estimated = False
        n += 1
    return n


def _as_release(color, got: Slide, off_rel: float = 0.0, off_tee: float = 0.0):
    # The climb, on the fitted line and the tee's correction: it is what the
    # thinking clock and the broom read the tee crossing from.
    track = tuple((got.t_at(y) + off_tee, got.x_m, y)
                  for y in (FIT_Y_M[0], REF_Y_M, 0.0, FIT_Y_M[1]))
    return R.Release(color, got.t_ref + off_rel, got.y_max_m, got.speed_m_s,
                     track=track, source=SOURCE)


# -- Rocks the overhead saw at neither end -------------------------------------
#
# The scan's rate. Half the fill-in's: a slide at 2 m/s spends 3 s in FIT_Y_M,
# so 5 fps still gives it about 15 samples against FIT_MIN_N of 4, and on
# PHbZ3EKOhMI it found the same 94 slides at 5 fps as the fill-in's windows do
# at 10. The scan reads far more video than a fill-in, so the rate is its cost.
SCAN_FPS = 5.0
# Decoded this much at a time: the view's frames are full RGB, ~2.6 MB each.
SCAN_CHUNK_S = 20.0
# Slides are fitted in windows this long, stepped this far, and two fits of
# one colour closer than SAME_SLIDE_S are one slide, the better-sampled kept.
# A slide crosses FIT_Y_M in about 3 s; two throws are never within
# R.MIN_SEPARATION_S of each other.
SLIDE_WINDOW_S = 6.0
SLIDE_STEP_S = 1.0
SAME_SLIDE_S = 3.0
# Where to look, as multiples of the end's median time between rocks: a gap
# this long between two rocks seen can hold one that was not, and the search
# reaches this far before the first rock seen and after the last. Bounded
# rather than running to the end's edges, because between games players slide
# practice rocks, and the first end's run-up reaches back into that.
# PHbZ3EKOhMI end 6's lost rock 1 was 59 s, 1.1 of its end's median, before
# the first rock seen.
GAP_FACTOR = 1.7
# An end's median before it has two gaps to take one from.
DEFAULT_INTERVAL_S = 55.0
# After the last rock seen, the search reaches this many gaps on: an end that
# lost both of its last two rocks hides the hammer two intervals out.
# Rochester sheet B 10/28 (6IUB9KbPkpc) end 7: rock 15 was found 78 s after
# rock 14, inside one reach, and blue's hammer slid 143 s after it, past it.
# What lies beyond an end's last rock is the next end, thrown toward this
# camera, which a slide (moving away from it) never matches.
TAIL_REACHES = 2
# A slide must be surer to add a rock than to time one: it has to run this
# far, and reach the tee. The fill-in knows a rock is there and asks only for
# FIT_MIN_SPAN_M. Scanning every end of five games (PHbZ3EKOhMI, bLkgfZaDSKw,
# 2z7vOezY9Bw and qMDNIgIGHZs of 2026-09-27, VXU9xwmugRg of the spring; 32
# ends) found 494 slides of rocks the timelines hold, 2 of them short of
# this, lost to their sweepers; 4 slides where a timeline had a blank, all
# 3.65-5.54 m and past +2.6 m; and 2 with no rock behind them at all, 1.46 m
# to -0.58 m and 1.74 m to -1.25 m.
LOST_MIN_SPAN_M = 2.0
LOST_MIN_Y_MAX_M = 0.0
# ...and slide faster than a stone pushed by hand. Of those 494, 5 slid under
# this (0.82-1.04 m/s) and the median 2.11; the four rocks found where a
# timeline had a blank slid at 1.95-2.24; the five stones seen pushed through
# a throwing house between ends slid at 0.81-1.02.
LOST_MIN_SPEED_M_S = 1.1
# ...and be seen without a break this long. Rochester sheet C (vztdzCNM2fk)
# end 2: three yellows at rest in the throwing house, 2.4 m apart down the
# sheet, lined up as two "slides" at 1.2 m/s (13:51 and 14:06), one sample
# where the line met each stone and 1.4-2.0 s between them. Real slides there
# were seen every frame (0.2 s apart at SCAN_FPS); this allows three missed.
LOST_MAX_GAP_S = 0.8
# The gaps are whole frames at SCAN_FPS, summed in floats: three missed comes
# out 0.8000000000002 as often as 0.7999999999997, and a bare `<=` failed the
# first. Rochester sheet B 11/18 (QU4XN1R19TA) end 4 rock 3, a blue thrown at
# 54:03 and lost for three frames at one place: the count came to 15, was not
# used, and the end was built red first with its hammer on the wrong team.
# A quarter of a frame keeps three missed on one side and four on the other.
LOST_GAP_SLACK_S = 0.25 / SCAN_FPS
# The search starts this long after the end's run-up does, which is the
# previous end's last rock coming to rest. That house is this end's throwing
# house, and it is being cleared: on bLkgfZaDSKw, the 6 s after end 1's last
# rest held four slides of both colours at 0.8-1.0 m/s, the players pushing
# end 1's stones. The quickest turnaround in five games (27 of them) threw the
# next rock 32.8 s after the close, the median 55 s.
# Not the video's first end, where nothing closed: its run-up is the
# recording's start (`analyze`), and the stream may come up as its first rock
# slides (Rochester sheet B 10/28, 6IUB9KbPkpc: blue's, 0.7 s in).
TURNAROUND_S = 20.0
# Release to arrival, for an arrival with no release to time it by: the middle
# of the 11-24 s the overhead measures.
TYPICAL_LAG_S = 17.0


def scan_points(video, view, t0, t1, *, fps=SCAN_FPS, model=None, decode=None,
                detect=None) -> dict:
    """Both colours' centre-line points over ``t0..t1``, as ``side_points``
    gives one colour's: each stretch of video is decoded once and read by the
    detector once, for both.

    The detector's boxes carry their colour, so one pass over a stretch gives
    both colours' (`sidemodel.detect_bands`); a pass a colour read every frame
    twice, and the scan is the largest part of a census end. The stretches are
    the same ones, decoded by the same commands, each while the one before it
    is read (`longview.Plan`): the GPU sat idle through every decode.
    Rochester sheet B 11/18 (QU4XN1R19TA) end 1 on an Apple GPU: the scan was
    112 s of the end's 258, the detector 69 of them on 5,750 frames read
    twice and the decodes 30; it is 45 s so, and the end built from it the
    same in every field.
    """
    from contextlib import nullcontext

    from curling_score.detect import longview, sidemodel

    spans = []
    t = t0
    while t < t1:
        spans.append((t, min(t + SCAN_CHUNK_S, t1)))
        t += SCAN_CHUNK_S
    ahead = nullcontext()
    if decode is None:
        decode = longview.Plan(video, [(view.rect, a, b, fps) for a, b in spans]).decode
        ahead = longview.reading_ahead()
    if detect is None:
        both = sidemodel.detect_bands
    else:
        # A stand-in for one colour, asked once per colour.
        def both(model, frames, times, lo, hi, colors):
            return [detect(model, frames, times, lo, hi, c) for c in colors]
    if model is None:
        model = sidemodel.default_model()
    top, bot = _band(view)
    out = {"red": [], "yellow": []}
    with ahead:
        for a, b in spans:
            frames, times = decode(video, view.rect, a, b, fps)
            if len(frames):
                for color, boxes in zip(out, both(model, frames, times, top, bot, tuple(out))):
                    out[color] += stone_points(view, times, boxes)
    return out


def find_slides(points, t0, t1) -> list[Slide]:
    """Every distinct slide in one colour's ``points`` over ``t0..t1``, in time
    order: ``fit_slide`` in each window, one slide per SAME_SLIDE_S."""
    points = sorted(points)
    found: list[Slide] = []
    w = t0
    while w < t1:
        got = fit_slide([q for q in points if w <= q[0] < min(w + SLIDE_WINDOW_S, t1)])
        if got is not None:
            same = [i for i, s in enumerate(found) if abs(s.t_ref - got.t_ref) < SAME_SLIDE_S]
            if not same:
                found.append(got)
            elif got.n > found[same[0]].n:
                found[same[0]] = got
        w += SLIDE_STEP_S
    return sorted(found, key=lambda s: s.t_ref)


# An end's rocks are never thrown closer together than this on average: the
# floor under an interval worked out from an end's span (`search_windows`).
MIN_INTERVAL_S = 45.0


def search_windows(rocks, t0, t1, per_end=None) -> list[tuple[float, float]]:
    """Where an end short of rocks could be hiding one, given ``(t, colour)``
    for when each rock it has was thrown: before the first, after the last,
    between two of a colour -- the other team's rock must lie between them --
    and inside any other gap GAP_FACTOR times the end's median. Each window
    keeps R.MIN_SEPARATION_S clear of the rocks either side of it, and none
    leaves ``t0..t1``.

    The colour rule is not the gap rule's to catch: s_1aAUMPjTB3eCfHqHM end 2
    lost a red between two yellows 87 s apart, when its reach was 88 s.

    The median gap of an end missing several rocks is already two rocks long,
    and a gap holding one lost rock then looks ordinary: Rochester sheet A
    11/4 end 5 (rocks 2 and 3, 122 s between a red and a blue against a reach
    of 147 s) and sheet C 11/11 end 2 (three rocks in gaps of 100 and 158 s
    against 170 s). So with ``per_end`` given and the end short of it, a gap
    between two rocks is judged by the smaller of the median and the end's
    span shared among ``per_end`` rocks, never under MIN_INTERVAL_S (an end
    the stream cut off has a short span and all its rocks). The reaches
    before the first rock and after the last keep the median: a shorter one
    there would only look less far."""
    rocks = sorted(rocks)
    if not rocks:
        return [(t0, t1)] if t1 > t0 else []
    ts = [t for t, _c in rocks]
    gaps = [b - a for a, b in zip(ts, ts[1:])]
    interval = sorted(gaps)[len(gaps) // 2] if len(gaps) >= 2 else DEFAULT_INTERVAL_S
    reach = GAP_FACTOR * interval
    between = reach
    if per_end and 2 <= len(rocks) < per_end:
        shared = max((ts[-1] - ts[0]) / (per_end - 1), MIN_INTERVAL_S)
        between = GAP_FACTOR * min(interval, shared)
    sep = R.MIN_SEPARATION_S
    spans = [(ts[0] - reach, ts[0] - sep)]
    spans += [(a + sep, b - sep) for (a, ca), (b, cb) in zip(rocks, rocks[1:])
              if b - a >= between or ca == cb]
    spans.append((ts[-1] + sep, ts[-1] + TAIL_REACHES * reach))
    out = []
    for a, b in spans:
        a, b = max(a, t0), min(b, t1)
        if b - a >= SLIDE_WINDOW_S / 2:
            out.append((a, b))
    return out


def rock_times(kept, thrown_by, lags=()) -> list[tuple[float, str]]:
    """``(t, colour)`` for when each rock in ``kept`` was thrown: its release
    where one was paired with it (``thrown_by`` maps a release to its
    arrival), the arrival itself for a rock ``detect.release`` stood in for,
    whose arrival *is* its release, and otherwise the arrival less the end's
    median lag."""
    by_arrival = {id(d): r.t for r, d in thrown_by.items()}
    lags = sorted(lags)
    lag = lags[len(lags) // 2] if lags else TYPICAL_LAG_S
    out = []
    for d in kept:
        if id(d) in by_arrival:
            t = by_arrival[id(d)]
        elif getattr(d, "reason", "") in R.RELEASE_REASONS:
            t = d.t_enter
        else:
            t = d.t_enter - lag
        out.append((t, d.color))
    return out


# One stone read in the other colour for part of its slide leaves a second,
# shorter slide beside the real one: the same moment, the other colour, at most
# this share of its sightings. Rochester sheet D 11/9 end 6 rock 1: blue, 13
# sightings over 5.35 m, with a "red" of 6 over 2.67 m 0.9 s after it -- and
# the two, being closer than two throws ever are, were both taken for stones
# being moved and the end's first rock was lost.
# 0.7, not 0.6: Rochester sheet B 11/18 (QU4XN1R19TA) end 3 rock 10 was blue,
# 13 sightings over 5.2 m, with a "red" of 8 over 4.0 m 0.7 s after it. At
# 0.62 of the blue it was no echo, both were dropped, and the count came to
# 15. Two slides as strong as each other (10 of 12) are still left alone.
ECHO_SHARE = 0.7


def could_be_a_throw(s) -> bool:
    """Whether a slide the throwing camera saw is one a throw could make: long
    enough, far enough up the sheet, fast enough, and seen all the way, with
    at most three frames missed in a row."""
    return (s.span_m >= LOST_MIN_SPAN_M and s.y_max_m >= LOST_MIN_Y_MAX_M
            and s.speed_m_s >= LOST_MIN_SPEED_M_S
            and s.max_gap_s <= LOST_MAX_GAP_S + LOST_GAP_SLACK_S)


def without_echoes(found):
    """``found`` -- ``(colour, Slide)`` pairs -- less each slide that is another
    colour's echo: within SAME_SLIDE_S of a slide of the other colour with
    enough more sightings (`ECHO_SHARE`). Two of a colour, or two as strong
    as each other, are left for the caller to judge."""
    return [(c, s) for c, s in found
            if not any(oc != c and abs(o.t_ref - s.t_ref) < SAME_SLIDE_S and s.n <= ECHO_SHARE * o.n
                       for oc, o in found)]


def census_is_clean(seen, per_end) -> bool:
    """Whether the throwing camera's slides are an end as the rules know one:
    ``per_end`` of them, the colours strictly in turn."""
    colours = [c for c, _s in seen]
    return len(colours) == per_end and all(a != b for a, b in zip(colours, colours[1:]))


def census_candidates(seen, timed, tol_s=R.MIN_SEPARATION_S):
    """For each slide of the throwing camera's count, the candidate that is
    that throw, or None: ``timed`` is ``(t_release, candidate)`` for every
    candidate a release stands behind, and a slide's is the nearest in time of
    its own colour within ``tol_s``, each candidate taken once. The slide's
    colour decides: the camera behind the thrower sees the handle from a
    stone's length away, and a release the overhead read in the other colour
    is not this throw's."""
    used, out = set(), []
    for color, s in seen:
        near = [(abs(t - s.t_ref), k) for k, (t, d) in enumerate(timed)
                if k not in used and d.color == color and abs(t - s.t_ref) < tol_s]
        if near:
            k = min(near)[1]
            used.add(k)
            out.append(timed[k][1])
        else:
            out.append(None)
    return out


def release_of(color, slide):
    """A slide the count found, as the release the rest of the pipeline reads."""
    return _as_release(color, slide)


def lost_rocks(video, view, *, kept, releases, thrown_by, arrivals, house_frames,
               t0, t1, scan=None, vouched=None, per_end=None, whole=False, seen=None,
               pairs=None, turnaround_s=TURNAROUND_S) -> list:
    """The rocks an end the rules left short lost at both ends of the sheet, as
    deliveries ``fit.fit_end`` can place; [] when there are none.

    ``kept`` is the end as the rules built it, ``releases`` every overhead
    release, ``thrown_by`` their pairing to ``arrivals``, the far house's
    candidates, and ``house_frames`` its detections. ``t0`` is where the end's
    run-up begins, and the search starts ``turnaround_s`` after it (0 for the
    video's first end, TURNAROUND_S after any other); it never passes ``t1``. Only a slide a throw could make counts: LOST_MIN_SPAN_M
    long, reaching LOST_MIN_Y_MAX_M, and no other slide within
    R.MIN_SEPARATION_S of it. A slide within R.MIN_SEPARATION_S of an overhead
    release is that release, whatever colour either read; one that pairs with
    an arrival no release claimed is that arrival's lost release, which the
    fill-in times later. Whatever is left is settled by ``R.unaccounted`` exactly as an
    overhead release with no arrival would be: from what the house did, a
    rock that arrived unseen, struck a stone, or was hogged.

    ``vouched``, a set, receives the ``id`` of each arrival a found slide
    pairs with: that arrival was thrown, so ``fit.drop_clearing`` must not
    take it for a stone moved while the house was cleared (Rochester sheet A
    end 4's hammer, a guard swept away a second after it stopped).

    ``per_end`` is the format's rocks an end, for `search_windows`.

    ``whole`` searches the end from its turnaround to ``t1``, not only where
    `search_windows` says a rock could be hiding, and ``seen``, a list, then
    receives every slide a throw could have made, ``(colour, Slide)`` in time
    order: the throwing camera's own count of the end, for a club whose
    overheads lose too much to say where the gaps are (`analyze`'s census).
    ``pairs``, a list, receives ``(release, arrival)`` for each found slide
    that pairs with an arrival.

    ``scan`` is ``(video, view, t0, t1) -> {colour: [(t, y, x)]}``,
    ``scan_points`` by default. A decode or detector error costs the end only
    what the search would have added.
    """
    if view is None or not getattr(view, "has_lateral", False):
        return []
    if scan is None:
        scan = scan_points
    lags = [d.t_enter - r.t for r, d in thrown_by.items()]
    windows = ([(t0 + turnaround_s, t1)] if whole and t1 > t0 + turnaround_s else
               search_windows(rock_times(kept, thrown_by, lags), t0 + turnaround_s, t1,
                              per_end=per_end))
    found = []
    for a, b in windows:
        try:
            pts = scan(video, view, a, b)
        except Exception:
            log.exception("long-camera search failed over %.0f-%.0f s", a, b)
            continue
        for color, p in pts.items():
            found += [(color, s) for s in find_slides(p, a, b) if could_be_a_throw(s)]
    found = without_echoes(found)
    # Two throws are never within R.MIN_SEPARATION_S of each other, so slides
    # that close together are stones being moved, and none of them is a throw.
    found = [(c, s) for c, s in found
             if not any(o is not s and abs(o.t_ref - s.t_ref) < R.MIN_SEPARATION_S
                        for _c, o in found)]
    if seen is not None:
        seen.extend(sorted(found, key=lambda f: f[1].t_ref))
    known = [r.t for r in releases]
    new = [_as_release(color, s) for color, s in sorted(found, key=lambda f: f[1].t_ref)
           if all(abs(s.t_ref - t) >= R.MIN_SEPARATION_S for t in known)]
    if not new:
        return []
    claimed = {id(d) for d in thrown_by.values()}
    free = [d for d in arrivals if id(d) not in claimed]
    pairing = R.pair(new, free)
    if vouched is not None:
        vouched.update(id(d) for d in pairing[0].values())
    if pairs is not None:
        pairs.extend(pairing[0].items())
    return R.unaccounted(new, free, house_frames, pairing=pairing)
