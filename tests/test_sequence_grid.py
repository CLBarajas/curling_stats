"""Detection spans start on the video's own frame grid, wherever they are asked to."""
import pytest

from curling_score.detect import sequence


def test_a_start_goes_back_to_the_last_whole_step_of_the_video():
    assert sequence.on_grid(4349.35, 5.0) == pytest.approx(4349.2)
    assert sequence.on_grid(4349.4, 5.0) == pytest.approx(4349.4)
    assert sequence.on_grid(4349.399999, 5.0) == pytest.approx(4349.2)
    assert sequence.on_grid(6317.28, 10.0) == pytest.approx(6317.2)
    assert sequence.on_grid(0.07, 5.0) == 0.0
    assert sequence.on_grid(-3.0, 5.0) == 0.0


def test_two_spans_a_thirtieth_of_a_second_apart_sample_the_same_frames(monkeypatch):
    """Rochester sheet B 10/28 end 8: its run-up opened 0.033 s later in one
    run than another, every frame moved with it, and its first rock was lost."""
    asked = []

    def chunked(path, start_s, end_s, fps, size, crop):
        asked.append(start_s)
        return iter(())

    monkeypatch.setattr(sequence.F, "chunked", chunked)

    class Setup:
        rect, calib = (0, 0, 10, 10), None

    for start in (6317.25, 6317.283):
        sequence.detect_span("v.mp4", Setup(), start, 6400.0, 5.0, use_cache=False)
    assert asked == [pytest.approx(6317.2)] * 2


def test_a_live_end_s_spans_start_on_the_grid_too(monkeypatch):
    seen = {}

    def windows(path, specs, end_s):
        seen["starts"] = [start for start, _fps, _crop in specs]
        return iter(())

    monkeypatch.setattr(sequence.F, "windows", windows)

    class Setup:
        rect, calib = (0, 0, 10, 10), None

    sequence.detect_spans("v.mp4", [(Setup(), 100.13, 5.0), (Setup(), 90.07, 10.0)], 200.0)
    assert seen["starts"] == [pytest.approx(100.0), pytest.approx(90.0)]
