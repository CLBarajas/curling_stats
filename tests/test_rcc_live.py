"""Rochester's live run and its sheet C end camera (2026-11-11).

- `analyze._end_views` keeps the end camera that fits when the other cannot
  (sheet C's right camera has no hog line in its picture).
- The live session compares calibrations only across the same cameras.
- The live pipeline reads the club's own board and guard timing.
- `cli._live_club` narrows a club to a sheet's profile by channel.
"""

from types import SimpleNamespace

import numpy as np
import pytest

from curling_score import analyze, clubs
from curling_score.geometry import sideview
from curling_score.live import session as live


def _view(tee=400.0, hog=800.0):
    return SimpleNamespace(tee_row=tee, hog_row=hog, d_m=16.0, has_lateral=True)


class TestEndViews:
    def _run(self, monkeypatch, fails):
        def solve(plate, rect, paint, name, end_camera):
            if name.split()[0] in fails:
                raise sideview.SideViewError("no dark hog line in view")
            return SimpleNamespace(view=_view(), ring_residual_m=0.01, centre_rows=150)
        monkeypatch.setattr(analyze.endcam, "solve", solve)
        monkeypatch.setattr(analyze, "_side_rects",
                            lambda panels, club, w, h: {"left": (0, 0, 10, 10), "right": (10, 0, 10, 10)})
        frames = [np.zeros((20, 20, 3), dtype="uint8")] * 2
        said = []
        views = analyze._end_views(frames, SimpleNamespace(), clubs.CLUBS["rochester-c"], said.append)
        return views, said

    def test_both_cameras_fit_as_before(self, monkeypatch):
        views, _ = self._run(monkeypatch, fails=())
        assert set(views) == {"left", "right"}

    def test_one_camera_that_cannot_be_fitted_leaves_the_other(self, monkeypatch):
        views, said = self._run(monkeypatch, fails=("right",))
        assert set(views) == {"left"}
        assert any("unusable, left out" in s for s in said)

    def test_neither_fitted_is_no_views(self, monkeypatch):
        views, said = self._run(monkeypatch, fails=("left", "right"))
        assert views is None
        assert any("no splits" in s for s in said)


class TestCalibrationAgreement:
    def _cal(self, views):
        setups = {"top": SimpleNamespace(hog_line=1.0), "bottom": SimpleNamespace(hog_line=1.0)}
        return live.Calibration(panels=None, setups=setups, sideviews=views, until_s=900.0)

    def test_one_camera_each_agrees(self):
        assert self._cal({"left": _view()}).agrees_with(self._cal({"left": _view(tee=402.0)}))

    def test_different_cameras_do_not_agree_and_do_not_raise(self):
        one, both = self._cal({"left": _view()}), self._cal({"left": _view(), "right": _view()})
        assert not one.agrees_with(both)
        assert not both.agrees_with(one)


class TestVideoPipelineClub:
    def test_the_board_is_the_clubs(self, monkeypatch):
        got = {}
        monkeypatch.setattr(analyze, "board_for_game",
                            lambda path, game, progress=None, **kw: got.update(kw))
        club = clubs.CLUBS["rochester-c"]
        live.VideoPipeline(club=club).read_board("v.ts", SimpleNamespace(index=0))
        assert got == {"board": club.board}

    def test_without_a_club_the_board_is_the_default(self, monkeypatch):
        got = {}
        monkeypatch.setattr(analyze, "board_for_game",
                            lambda path, game, progress=None, **kw: got.update(kw))
        live.VideoPipeline().read_board("v.ts", SimpleNamespace(index=0))
        assert got == {}


class TestLiveClub:
    def test_no_club_is_none(self):
        from curling_score import cli
        assert cli._live_club(None) is None

    def test_rochester_is_narrowed_to_the_sheet_by_channel(self):
        from curling_score import cli
        assert cli._live_club("rochester", "UCsAcOSWFFZDKce1DL5umYOA").name == "rochester-c"

    def test_a_sheet_profile_is_kept(self):
        from curling_score import cli
        assert cli._live_club("rochester-c").name == "rochester-c"

