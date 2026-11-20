"""The destination hog line from an end camera, for a house-only overhead (game.fartime)."""
from types import SimpleNamespace

import pytest

from curling_score.game import fartime, split
from curling_score.geometry import constants as C
from tests.test_endcam import TRUE

VIEW = TRUE.__class__(**{**TRUE.__dict__, "end_camera": True})
LINE_M = C.TEE_TO_HOGLINE_M + 2 * C.STONE_RADIUS_M      # the near edge as the leading edge crosses


def coming_in(t0, speed, *, col=300.0, until=2.0, y_from=6.9):
    """Box samples (t, bottom_row, width, cx) of a stone coming in from the view's edge."""
    out = []
    for i in range(int(until * 30)):
        t = t0 + i / 30
        y = y_from - speed * (t - t0)
        row = VIEW.row_for(y)
        if row < VIEW.rect[3]:
            out.append((t, min(row, VIEW.rect[3] - 1.0), 50.0, col))
    return out


def parked(y, t0, *, col=300.0, until=6.0):
    return [(t0 + i / 30, VIEW.row_for(y), 50.0, col) for i in range(int(until * 30))]


class TestEndCameraCrossing:
    def test_times_the_leading_edge_from_the_first_frames_in_view(self):
        got = fartime.end_camera_crossing({2: coming_in(110.0, 2.0)}, VIEW, 105.0)
        assert got[0] == pytest.approx(110.0 + (6.9 - LINE_M) / 2.0, abs=0.02)
        assert got[1] == pytest.approx(2.0, abs=0.05)

    def test_a_stone_parked_in_the_same_column_does_not_take_over(self):
        tracks = {2: sorted(parked(5.9, 105.0) + coming_in(110.0, 1.8))}
        got = fartime.end_camera_crossing(tracks, VIEW, 105.0)
        assert got[0] == pytest.approx(110.0 + (6.9 - LINE_M) / 1.8, abs=0.03)

    def test_a_parked_stone_alone_is_no_crossing(self):
        assert fartime.end_camera_crossing({2: parked(6.0, 105.0)}, VIEW, 105.0) is None


class TestTimeFromEndCamera:
    def test_fills_only_the_shots_the_panels_did_not_time(self):
        timed = SimpleNamespace(color="red", t_hog_s=100.0, far_crossing=split.FarCrossing(t=111.0))
        untimed = SimpleNamespace(color="red", t_hog_s=100.0, far_crossing=split.FarCrossing(t=None, v_near=2.0))
        windows = []

        def decode(video, rect, t0, t1, fps):
            windows.append((t0, t1))
            return [0], [t0]

        n = fartime.time_far_crossings_from_end_camera(
            [timed, untimed], "v.mp4", VIEW, model=object(), decode=decode,
            propose=lambda *a, **k: {2: coming_in(110.0, 2.0)})
        assert n == 1 and windows == [(105.0, 120.0)]
        assert timed.far_crossing.t == 111.0
        assert untimed.far_crossing.t == pytest.approx(110.0 + (6.9 - LINE_M) / 2.0, abs=0.02)
        assert untimed.far_crossing.v_near == 2.0

    def test_leaves_a_long_camera_alone(self):
        shot = SimpleNamespace(color="red", t_hog_s=100.0)
        assert fartime.time_far_crossings_from_end_camera([shot], "v.mp4", TRUE, model=object()) == 0


class TestReadNoFurtherThanTheCrossing:
    """The run's own read: a window given to the detector a batch at a time,
    stopping at the crossing, finds what a read of the whole window finds."""

    T0, SECONDS = 105.0, 15.0

    def window(self, tracks):
        """A window's frames (each its own index), its times, and a detector
        that answers for just the frames it is handed, counting them."""
        times = [self.T0 + i / 30 for i in range(int(self.SECONDS * 30))]
        by_frame = {}
        for key, track in tracks.items():
            for t, row, w, cx in track:
                i = round((t - self.T0) * 30)
                if 0 <= i < len(times):
                    by_frame.setdefault(i, []).append((key, (times[i], row, w, cx)))
        read = []

        def propose(model, frames, view, color, part_times):
            assert list(part_times) == [times[int(i)] for i in frames]
            read.extend(int(i) for i in frames)
            out = {}
            for i in frames:
                for key, p in by_frame.get(int(i), ()):
                    out.setdefault(key, []).append(p)
            return out
        whole = {}
        for i in sorted(by_frame):
            for key, p in by_frame[i]:
                whole.setdefault(key, []).append(p)
        return list(range(len(times))), times, propose, read, whole

    def as_read(self, monkeypatch, tracks):
        from curling_score.detect import sidemodel
        frames, times, propose, read, whole = self.window(tracks)
        monkeypatch.setattr(sidemodel, "propose", propose)
        got = fartime._crossing_as_read(object(), frames, times, VIEW, "red", self.T0)
        want = fartime.end_camera_crossing(
            sidemodel.split_at_gaps(whole, sidemodel.STRADDLE_GAP_MAX_S), VIEW, self.T0)
        return got, want, read, len(frames)

    def test_it_stops_at_the_crossing_and_times_it_the_same(self, monkeypatch):
        from curling_score.detect import sidemodel
        got, want, read, n = self.as_read(monkeypatch, {2: coming_in(110.0, 2.0)})
        assert want is not None and got == want
        # Seen 5 s into the window; read to the batch that holds its FIT_S, no further.
        assert read == list(range(len(read))) and len(read) % sidemodel.BATCH == 0
        assert (110.0 - self.T0 + fartime.FIT_S) * 30 <= len(read) < n / 2

    def test_a_parked_stone_first_does_not_stop_it_early(self, monkeypatch):
        tracks = {2: sorted(parked(5.9, self.T0, until=12.0) + coming_in(112.0, 1.8))}
        got, want, read, n = self.as_read(monkeypatch, tracks)
        assert want is not None and got == want

    def test_a_window_with_no_crossing_is_read_to_its_end(self, monkeypatch):
        got, want, read, n = self.as_read(monkeypatch, {2: parked(6.0, self.T0, until=15.0)})
        assert got is None and want is None and len(read) == n

    def test_whatever_the_boxes_the_answer_is_the_whole_read_s(self, monkeypatch):
        """Stray boxes at the view's edge, stones parked, a stone coming in at
        any moment or none: 300 windows, each read both ways."""
        import numpy as np
        rng = np.random.default_rng(7)
        found = stopped = 0
        for _ in range(300):
            tracks = {}
            if rng.random() < 0.8:
                tracks[2] = coming_in(self.T0 + rng.uniform(0.0, 14.8), rng.uniform(0.4, 4.5),
                                      col=float(rng.uniform(250, 350)), y_from=rng.uniform(6.6, 7.0))
            for _k in range(rng.integers(0, 3)):
                tracks.setdefault(int(rng.integers(0, 5)), []).extend(
                    parked(rng.uniform(4.5, 6.9), self.T0 + rng.uniform(0.0, 10.0),
                           col=float(rng.uniform(100, 500)), until=rng.uniform(0.2, 15.0)))
            for _k in range(rng.integers(0, 40)):      # strays: one box, anywhere near the edge
                t = self.T0 + int(rng.integers(0, 450)) / 30
                tracks.setdefault(int(rng.integers(0, 5)), []).append(
                    (t, VIEW.row_for(rng.uniform(5.5, 6.95)), 50.0, float(rng.uniform(100, 500))))
            tracks = {k: sorted(v) for k, v in tracks.items()}
            got, want, read, n = self.as_read(monkeypatch, tracks)
            assert got == want
            found += want is not None
            stopped += len(read) < n
        assert found > 100 and stopped > 100        # the test met both kinds of window
