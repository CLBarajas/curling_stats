"""When each stone crossed the throwing end's hog line, read from a side view.

This is the throwing end only. The target end's crossing comes from the
playing panel's own tripwire and is reliable -- one miss in 48 -- whereas the
throwing end's fails on 40% of shots because the thrower and sweepers stand
between the overhead camera and the stone.

Runs after the rules have settled the shot list, and like
``thinking.time_shots`` it may only attach a time to a rock already in it.
Nothing here can add, drop or renumber a shot.
"""

from curling_score.detect import longview, sidemodel

# Which side camera watches a given panel's hog line: the one at the *other*
# end, looking back. A camera never sees its own hog line -- that sits about
# half a metre beneath it, out of frame. Same alternation as ``OTHER_HOUSE``.
CAMERA_FOR = {"top": "left", "bottom": "right"}

# For a shot whose throw was never seen leaving the house, the arrival is the
# only anchor. Measured across three ends, a stone reaches the far panel 12-21 s
# after its release and crosses the hog line 3-5 s after that, which puts the
# crossing 8-20 s before the arrival. A wide window, so the refusals matter
# more here than anywhere else.
ARRIVAL_LOOKBACK_S = (8.0, 20.0)


# The rate ``find`` reads at when it is not told one (`sidemodel.find_crossing`):
# what the next rock's window is decoded ahead at.
READ_FPS = 30.0


def window_for(shot):
    """The span searched for a shot's crossing, ``(t0, t1)``: after its
    release, or before its arrival when no release was seen. None to leave
    the shot be."""
    if getattr(shot, "missing", False):
        return None
    release = getattr(shot, "release", None)
    if release is not None:
        return release.t + longview.WINDOW_S[0], release.t + longview.WINDOW_S[1]
    delivery = getattr(shot, "delivery", None)
    if delivery is None:
        return None
    return (delivery.t_enter - ARRIVAL_LOOKBACK_S[1],
            delivery.t_enter - ARRIVAL_LOOKBACK_S[0])


def time_hog_crossings(shots, video, view, *, find=None) -> None:
    """Give every shot its throwing-end hog crossing, in place.

    ``find`` defaults to the side-view detector; with it switched off
    (``none``) no shot is given one. Resolved per call rather than as a default
    argument value, so the model is not loaded by importing this module and a
    test can still pass its own.
    """
    if find is None:
        find = sidemodel.default_finder()
        if find is None:
            return
    todo = [(shot, win) for shot in shots if (win := window_for(shot)) is not None]
    for i, (shot, (t0, t1)) in enumerate(todo):
        # The next rocks' windows decode while this one's is searched
        # (`longview.reading_ahead`).
        for _ahead, win in todo[i + 1:i + 1 + longview.AHEAD]:
            longview.soon(video, view, *win, READ_FPS)
        got = find(video, view, shot.color, t0, t1)
        if getattr(got, "samples", ()):
            shot.hog_crossing = got
        if got:
            shot.t_hog_s = got.t
            # Carried so `split.long_split` can bound the pairing without a
            # release track. See `speed_at_hog` below.
            shot.v_hog_m_s = got.speed_m_s


def retime_released(shots, unreleased, video, view, *, find=None) -> int:
    """Read again, from its release, the crossing of each shot in
    ``unreleased`` that has a release now; return how many were read.

    ``unreleased`` is the shots that had no release when `time_hog_crossings`
    ran, so their windows hung off the arrival (ARRIVAL_LOOKBACK_S). The long
    camera (`sidereleases`) fills in releases after that pass, and a release
    is the better anchor. On an overhead that shows the house only, the arrival
    is late: on Rochester's sheet A (Go_JOSxJPsQ, 2026-11-11) 16 rocks reached
    the overhead 20.2-27.2 s after their hog crossing, past the lookback's
    20 s, so no crossing was found; two more arrived 19.5-19.7 s after, so
    their windows opened about 0.3 s before the stone reached the line. All 18
    kept their target broom but got no line, which is fitted to the
    crossing's track up to the hog line. Read from the release, 14 were timed
    and the other 4 still gave a track.

    The new read replaces the old whole, time and speed with it, when it has
    samples; a read with none leaves the shot as it was. Never adds, drops or
    renumbers a shot. ``shots`` is the end's list, for the signature's sake
    and to keep the rule plain: only shots in it are touched.
    """
    again = [s for s in unreleased if not getattr(s, "missing", False)
             and getattr(s, "release", None) is not None and any(s is x for x in shots)]
    if not again:
        return 0
    if find is None:
        find = sidemodel.default_finder()
        if find is None:
            return 0
    n = 0
    for i, shot in enumerate(again):
        for ahead in again[i + 1:i + 1 + longview.AHEAD]:
            longview.soon(video, view, *window_for(ahead), READ_FPS)
        got = find(video, view, shot.color, *window_for(shot))
        if not getattr(got, "samples", ()):
            continue
        shot.hog_crossing = got
        shot.t_hog_s = got.t
        shot.v_hog_m_s = got.speed_m_s
        n += 1
    return n


def crossing(shot):
    """When this shot crossed the throwing end's hog line, if it was seen to.

    Not named ``hog_crossing``: the panels time their own hog lines too
    (``split.line_crossing``), and two functions of one name timing the same
    line from different cameras is exactly the confusion to avoid.
    """
    return getattr(shot, "t_hog_s", None)


def speed_at_hog(shot):
    """How fast this shot was travelling at the throwing end's hog line, m/s.

    From the side view's own track through the perspective solve, so it is in
    real metres -- which is what lets it be compared against a distance.
    """
    return getattr(shot, "v_hog_m_s", None)
