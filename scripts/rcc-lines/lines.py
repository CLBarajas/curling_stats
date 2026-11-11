"""The hog, line, release and aim-line passes on one end of a finished
timeline, without re-running the game: each rock's shot is rebuilt from the
timeline (release, broom, rest) and the passes run on the real video.

    PYTHONPATH=src python scripts/rcc-lines/lines.py out/rcc-1104-fit/timeline.json 1 \\
        --json out/rcc-lines/end1.json

About 12 s a rock on the CPU. Prints a row a rock; --json keeps every line.
The release read is off on an end camera (`releasetime.model_fits`) and off
without a GPU; to see what a model makes of these cameras anyway, name it and
ask for the CPU: CURLING_SCORE_RELEASE_WEIGHTS=weights/release1.pt
CURLING_SCORE_RELEASE_CPU=1.
"""
import argparse
import json
import pathlib
import sys
from types import SimpleNamespace

from curling_score import timeline as timeline_mod
from curling_score.detect import longview, releasemodel, sidemodel
from curling_score.game import aimlines, hogtime, linetime, releasetime
from curling_score.game.broomtime import TargetBroom
from curling_score.geometry.sideview import SideView

OTHER = {"top": "bottom", "bottom": "top"}


def view_from(c):
    return SideView(rect=tuple(c["rect"]), tee_row=c["tee_row"], hog_row=c["hog_row"], d_m=c["d_m"],
                    centre_col=c["centre_col"], lat_px_per_m_at_tee=c["lat_px_per_m_at_tee"],
                    centre_line=tuple(c["centre_line"]), end_camera=bool(c.get("end_camera")))


def shot_from(s):
    b = s.get("target_broom")
    return SimpleNamespace(
        number=s["number"], color=s["color"], missing=s["missing"] or s.get("t_release_s") is None,
        release=None if s.get("t_release_s") is None else SimpleNamespace(t=s["t_release_s"]),
        delivery=None, hog_crossing=None, t_hog_s=None, line=None,
        target_broom=None if b is None else TargetBroom(b["x"], b["y"], b["seen"], b["confidence"]),
        t_rest_s=s.get("t_rest_s"), delivered_stone_index=s.get("delivered_stone_index"),
        stones=[SimpleNamespace(x_m=st["x"], y_m=st["y"]) for st in s.get("stones") or []])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("timeline")
    ap.add_argument("ends", type=int, nargs="+")
    ap.add_argument("--video", default=str(pathlib.Path.home() / ".cache/curling_score/videos/Go_JOSxJPsQ.mp4"))
    ap.add_argument("--side", default="weights/rcc2b.pt")
    ap.add_argument("--without-broom", action="store_true")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    doc = json.load(open(a.timeline))
    views = {n: view_from(doc["calibration"][n]) for n in ("left", "right")}
    side = sidemodel._load(a.side)
    release_model = releasemodel.default_model()
    print("release model:", "on" if release_model is not None else "off (CURLING_SCORE_RELEASE_CPU=1 to run it here)")
    find = lambda video, view, color, t0, t1, fps=30.0: sidemodel.find_crossing(side, video, view, color, t0, t1, fps)
    out = {}
    for number in a.ends:
        end = next(e for e in doc["games"][0]["ends"] if e["number"] == number)
        dest = views[hogtime.CAMERA_FOR[end["house"]]]
        hog = views[hogtime.CAMERA_FOR[OTHER[end["house"]]]]
        shots = [shot_from(s) for s in end["shots"]]
        keeper = releasetime.keeper_for(shots, hog, release_model)
        with longview.keeping(keeper):
            hogtime.time_hog_crossings(shots, a.video, hog, find=find)
            n_lines = linetime.time_lines(shots, a.video, hog, dest, model=side, without_broom=a.without_broom)
        n_rel = releasetime.time_releases(shots, keeper, hog, model=release_model) if keeper is not None else 0
        n_aim = aimlines.attach_aim_lines(shots)
        print(f"end {number}: lines {n_lines}/{len(shots)}, releases {n_rel}, release lines {n_aim}")
        for s in shots:
            l = s.line
            if l is None:
                why = ("missing" if s.missing else "no broom" if s.target_broom is None
                       else "no crossing samples" if s.hog_crossing is None else "no fit")
                print(f"  {s.number:2d} {s.color:6s} no line: {why}")
                continue
            j = timeline_mod._line(l)
            rel = l.release
            f = lambda a_: "   -  " if a_ is None or a_.miss is None else f"{a_.miss * 100:+5.0f}{'' if a_.shown else '?'}"
            print(f"  {s.number:2d} {s.color:6s} start {None if l.start is None else tuple(round(v, 2) for v in l.start)} "
                  f"delivery {len(l.delivery)} pts"
                  + (f" {linetime.TEE_Y - l.delivery[0][1]:+.1f}..{linetime.TEE_Y - l.delivery[-1][1]:+.1f} m" if l.delivery else "")
                  + f" | path {len(l.path)} pts"
                  + (f" y {l.path[0][0]:.1f}->{l.path[-1][0]:.1f} x {l.path[0][1]:+.2f}->{l.path[-1][1]:+.2f}" if l.path else "")
                  + f" | curl {l.curl} | release "
                  + ("-" if rel is None else f"{rel[0]:+.2f}s at {linetime.TEE_Y - rel[1]:.2f} m past tee")
                  + f" | slide {f(l.slide)} cm, release line {f(l.release_line)} cm")
            out[f"{number}.{s.number}"] = j
    if a.json:
        pathlib.Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        json.dump(out, open(a.json, "w"), indent=1)


if __name__ == "__main__":
    sys.exit(main())
