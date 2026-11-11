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
        with pytest.raises(fb.Unreadable, match="glyphs"):
            fb.read_image(image, BOARD)

    def test_someone_in_front_of_a_card_row_only(self, image):
        image[150:200, 800:840] = (120, 90, 60)     # neither a card nor bare board
        with pytest.raises(fb.Unreadable, match="bottom row"):
            fb.read_image(image, BOARD)

    def test_a_picture_that_is_not_the_board(self, image):
        image[:] = (200, 200, 200)
        with pytest.raises(fb.Unreadable):
            fb.read_image(image, BOARD)
