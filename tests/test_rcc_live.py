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
            return SimpleNamespace(view=_view(), ring_residual_m=0.01, centre_rows=150, hog_seen=True)
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


class TestALiveChartIsDrawnInTheClubsColours:
    """Rochester sheet B, 2026-11-18 (QU4XN1R19TA): the live chart came up
    with yellow stones and Granite's house paint, because only `analyze`
    handed the club's `stone_display` and `house_display` to the document."""

    def _doc(self, **pipe):
        from curling_score.game import format as format_mod
        s = live.LiveSession(
            "QU4XN1R19TA", "https://www.youtube.com/watch?v=QU4XN1R19TA",
            SimpleNamespace(head_s=lambda: 120.0), format_mod.FOURS,
            SimpleNamespace(processing_version=lambda sideviews: "test", **pipe), sheet="B")
        return s.document()

    def test_the_clubs_stones_and_houses_are_in_the_document(self):
        club = clubs.CLUBS["rochester-b"]
        doc = self._doc(club=club)
        assert doc["stones"] == club.stone_display == {"yellow": {"name": "Blue", "color": "#4d8ef0"}}
        assert doc["houses"] == club.house_display
        assert doc["houses"]["top"] == clubs.CLUBS["rochester"].house_display["bottom"]

    def test_a_club_with_none_of_its_own_writes_neither(self):
        assert not {"stones", "houses"} & set(self._doc(club=clubs.GRANITE))

    def test_no_club_at_all_writes_neither(self):
        assert not {"stones", "houses"} & set(self._doc())


class TestALiveEndIsCountedByTheThrowingCamera:
    """Rochester sheet B, 2026-11-18 (QU4XN1R19TA) end 1: red's last rock was
    never charted, and blue's hammer stood in its place. `analyze` counts a
    Rochester end from the camera behind the thrower (`throws_from_end_camera`);
    the live session built its ends without saying so."""

    def _context(self, **pipe):
        from curling_score.game import format as format_mod

        class Stop(Exception):
            pass

        got = []

        def build_end(ctx, game, end, run_up):
            got.append(ctx)
            raise Stop

        s = live.LiveSession(
            "QU4XN1R19TA", "https://www.youtube.com/watch?v=QU4XN1R19TA",
            SimpleNamespace(path="rec.0.ts", head_s=lambda: 1900.0), format_mod.FOURS,
            SimpleNamespace(build_end=build_end, **pipe), sheet="B")
        s.calibration = SimpleNamespace(setups={}, sideviews=None, until_s=900.0)
        with pytest.raises(Stop):
            s._build(SimpleNamespace(index=0), SimpleNamespace(number=1))
        return got[0]

    def test_rochester_counts(self):
        club = clubs.CLUBS["rochester-b"]
        assert club.throws_from_end_camera
        assert self._context(club=club).throws_from_end_camera is True

    def test_a_club_that_does_not_count_is_left_alone(self):
        assert self._context(club=clubs.GRANITE).throws_from_end_camera is False

    def test_no_club_is_left_alone(self):
        assert self._context().throws_from_end_camera is False


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

