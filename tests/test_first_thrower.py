"""The wall board says who throws an end's first rock; a missing first rock goes there."""

from types import SimpleNamespace

from curling_score.detect.delivery import Delivery
from curling_score.game import format as format_mod
from curling_score.game import shots
from curling_score import analyze


def dv(color, t):
    return Delivery(color=color, t_enter=t, t_rest=t + 8.0, entry_y_m=1.9,
                    rest_x_m=0.0, rest_y_m=0.0, travel_m=1.5, reason="rest")


def seen(n, first):
    other = "red" if first == "yellow" else "yellow"
    return [(first if i % 2 == 0 else other, dv(first if i % 2 == 0 else other, 45.0 * i))
            for i in range(n)]


class TestAMissingFirstRock:
    """Rochester's Go_JOSxJPsQ end 5: red threw first, as a guard no overhead
    saw; the fifteen rocks after it were all there, beginning with blue."""

    def test_by_itself_the_blank_goes_on_the_tail(self):
        got = shots._fill_short_end(seen(15, "yellow"), 16)
        assert len(got) == 16
        assert shots.unseen(got[-1][1]) and not shots.unseen(got[0][1])

    def test_told_who_threw_first_it_goes_in_front(self):
        got = shots._fill_short_end(seen(15, "yellow"), 16, first_color="red")
        assert len(got) == 16
        assert got[0][0] == "red" and shots.unseen(got[0][1])
        assert not any(shots.unseen(d) for _c, d in got[1:])
        assert [c for c, _d in got] == ["red", "yellow"] * 8

    def test_an_end_that_already_begins_with_that_team_keeps_its_tail_blank(self):
        got = shots._fill_short_end(seen(15, "red"), 16, first_color="red")
        assert not shots.unseen(got[0][1]) and shots.unseen(got[-1][1])

    def test_a_full_end_is_left_as_it_is(self):
        full = seen(16, "yellow")
        assert shots._fill_short_end(full, 16, first_color="red") == full

    def test_three_short_takes_one_in_front_and_leaves_the_pair_to_the_gaps(self):
        got = shots._fill_short_end(seen(13, "yellow"), 16, first_color="red")
        assert len(got) == 16 and got[0][0] == "red" and shots.unseen(got[0][1])


def end(number, hammer, observed=16):
    return {"number": number, "hammer": hammer, "shots_observed": observed, "shots_expected": 16}


def board(per_end):
    return SimpleNamespace(scores=SimpleNamespace(per_end=per_end))


class TestTheBoardSaysWhoThrowsFirst:
    FOURS = format_mod.FOURS

    def test_the_team_that_scored_throws_first(self):
        # Red had the hammer in end 1 and scored: yellow has it in end 2, red throws first.
        got = analyze.first_thrower_by_the_board(
            [end(1, "red")], board({1: {"red": 1, "yellow": 0}}), self.FOURS)
        assert got == "red"

    def test_a_steal_leaves_the_hammer_where_it_was(self):
        # Go_JOSxJPsQ: yellow had the hammer in end 4 and red stole three.
        ends = [end(1, "red"), end(2, "yellow"), end(3, "red"), end(4, "yellow")]
        scores = {1: {"red": 1, "yellow": 0}, 2: {"red": 0, "yellow": 4},
                  3: {"red": 1, "yellow": 0}, 4: {"red": 3, "yellow": 0}}
        assert analyze.first_thrower_by_the_board(ends, board(scores), self.FOURS) == "red"

    def test_nothing_without_a_board_or_before_the_first_end(self):
        assert analyze.first_thrower_by_the_board([end(1, "red")], None, self.FOURS) is None
        assert analyze.first_thrower_by_the_board([], board({}), self.FOURS) is None

    def test_nothing_when_an_end_so_far_is_not_posted(self):
        got = analyze.first_thrower_by_the_board(
            [end(1, "red"), end(2, "yellow")], board({1: {"red": 1, "yellow": 0}}), self.FOURS)
        assert got is None

    def test_nothing_when_the_first_ends_own_hammer_is_a_guess(self):
        got = analyze.first_thrower_by_the_board(
            [end(1, "red", observed=14)], board({1: {"red": 1, "yellow": 0}}), self.FOURS)
        assert got is None
