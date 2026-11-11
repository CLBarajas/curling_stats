"""A wall scoreboard with a camera of its own, read where the profile says it is."""

from pathlib import Path

import pytest

cv2 = pytest.importorskip("cv2")

from curling_score.game import fixedboard as fb  # noqa: E402
from curling_score.game import scoreboard as sb  # noqa: E402

# Rochester's sheet A board late in Go_JOSxJPsQ (2026-11-04), the median of
# thirty frames over ten minutes: seven ends posted, tied at seven.
IMAGE = Path(__file__).parent / "fixtures" / "fixedboard" / "rochester_a_after_7.png"
BOARD = fb.FixedBoard(rect=(322, 850, 1276, 226))


@pytest.fixture
def image():
    return cv2.imread(str(IMAGE))


class TestTheGeometryComesFromTheStrip:
    def test_the_strip_is_the_band_of_numerals(self, image):
        top, bottom = fb.strip_rows(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), BOARD)
        assert 80 <= top <= 95 and 125 <= bottom <= 140

    def test_eighteen_evenly_spaced_slots(self, image):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        xs, pitch = fb.slot_centres(gray, BOARD, fb.strip_rows(gray, BOARD))
        assert len(xs) == 18
        assert pitch == pytest.approx(54.2, abs=0.5)


class TestItReadsTheCards:
    def test_every_card_its_slot_and_its_end(self, image):
        got = fb.read_image(image, BOARD)
        assert [(c.slot, c.end) for c in got.red] == [(1, 1), (2, 3), (5, 4), (6, 5), (7, 7)]
        assert [(c.slot, c.end) for c in got.yellow] == [(4, 2), (7, 6)]

    def test_the_scoring_after_it_is_the_scoreboards_own(self, image):
        scores = sb.per_end_from_cards(fb.read_image(image, BOARD), 8)
        assert scores.per_end[2] == {"red": 0, "yellow": 4}
        assert scores.per_end[4] == {"red": 3, "yellow": 0}
        assert scores.unread_ends == (8,)
        assert scores.final is None   # the last end's card went up after the stream

    def test_the_rows_belong_to_the_teams_the_profile_names(self, image):
        swapped = fb.FixedBoard(rect=BOARD.rect, top="yellow", bottom="red")
        got = fb.read_image(image, swapped)
        assert [c.slot for c in got.yellow] == [1, 2, 5, 6, 7]
        assert [c.slot for c in got.red] == [4, 7]

    def test_a_numeral_the_classifier_is_unsure_of_is_a_card_with_no_end(self, image):
        got = fb.read_image(image, BOARD, predict=lambda glyph: (3, 0.5))
        assert [c.slot for c in got.red] == [1, 2, 5, 6, 7]
        assert all(c.end is None for c in got.red)


class TestItRefusesWhatItCannotSee:
    def test_someone_in_front_of_the_strip(self, image):
        image[60:226, 500:640] = (60, 70, 80)       # a grey jumper
        with pytest.raises(fb.Unreadable, match="numerals"):
            fb.read_image(image, BOARD)

    def test_someone_in_front_of_a_card_row_only(self, image):
        image[150:200, 800:840] = (120, 90, 60)     # neither a card nor bare board
        with pytest.raises(fb.Unreadable, match="bottom row"):
            fb.read_image(image, BOARD)

    def test_a_picture_that_is_not_the_board(self, image):
        image[:] = (200, 200, 200)
        with pytest.raises(fb.Unreadable):
            fb.read_image(image, BOARD)


# The other three sheets' boards, each the median of its board camera over
# eight minutes at the end of a game (2026-11-09 and 10), read through the
# sheet's own profile: their cameras frame the board differently (`datasets/rcc-sheets.md`).
OTHER_SHEETS = Path(__file__).parent / "fixtures" / "fixedboard"


def _read_sheet(name, profile):
    from curling_score import clubs

    return fb.read_image(cv2.imread(str(OTHER_SHEETS / name)), clubs.CLUBS[profile].board)


class TestTheOtherSheets:
    def test_sheet_b_a_soft_camera_whose_digits_run_together(self):
        # Df66u7Sv84c (2026-11-10), eight ends posted.
        got = _read_sheet("rochester_b_after_8.png", "rochester-b")
        assert [(c.slot, c.end) for c in got.red] == [(1, 3), (2, 4), (4, 5), (5, 6)]
        assert [(c.slot, c.end) for c in got.yellow][:3] == [(1, 1), (2, 2), (5, 7)]

    def test_sheet_bs_blur_leaves_its_8_short_of_the_bar(self):
        # The last card is there and in its slot, but its numeral reads 0.986:
        # a card with no end, so the game's last end goes unread.
        got = _read_sheet("rochester_b_after_8.png", "rochester-b")
        last = got.yellow[-1]
        assert last.slot == 6 and last.end is None and last.confidence > 0.9

    def test_sheet_c_a_close_camera_and_cards_hung_over_the_strip(self):
        # R-7qQORH0dQ
        got = _read_sheet("rochester_c_after_5.png", "rochester-c")
        assert [(c.slot, c.end) for c in got.red] == [(1, 1), (2, 2), (3, 4), (5, 5)]
        assert [(c.slot, c.end) for c in got.yellow] == [(2, 3)]

    def test_sheet_d_a_board_filling_the_picture(self):
        # Vu6sd-fo0PE
        got = _read_sheet("rochester_d_after_6.png", "rochester-d")
        assert [(c.slot, c.end) for c in got.red] == [(1, 2), (2, 4), (5, 6)]
        assert [(c.slot, c.end) for c in got.yellow] == [(3, 1), (4, 3), (6, 5)]

    def test_sheet_as_strip_does_not_read_sheet_cs_board(self):
        # 18 runs past sheet A's strip on C's board: the strip cut short there
        # has seventeen and a bit numerals, and the read is refused.
        with pytest.raises(fb.Unreadable):
            fb.read_image(cv2.imread(str(OTHER_SHEETS / "rochester_c_after_5.png")), BOARD)
