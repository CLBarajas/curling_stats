"""Why a rock on Rochester's end cameras gets no line, broom or spin: each
read's own functions run on one rock at a time, printing where it is refused.

    PYTHONPATH=src python scripts/rcc-lines/trace.py out/rcc-1104-fit/timeline.json 1 2 5 12 13

Needs the cached video and weights/; runs on the CPU (about a minute a rock).
Writes the broom window's middle frame, pads boxed, under --out.
"""
import argparse
import json
import pathlib
import sys
from types import SimpleNamespace

import numpy as np

from curling_score import weights as weights_mod
from curling_score.detect import broommodel, longview, sidemodel, spinmodel
from curling_score.game import broomtime, hogtime, linetime, spintime
from curling_score.geometry import constants as C
from curling_score.geometry.sideview import SideView, band_crop

OTHER = {"top": "bottom", "bottom": "top"}


def view_from(c):
    return SideView(rect=tuple(c["rect"]), tee_row=c["tee_row"], hog_row=c["hog_row"], d_m=c["d_m"],
                    centre_col=c["centre_col"], lat_px_per_m_at_tee=c["lat_px_per_m_at_tee"],
                    centre_line=tuple(c["centre_line"]), end_camera=bool(c.get("end_camera")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("timeline")
    ap.add_argument("end", type=int)
    ap.add_argument("rocks", type=int, nargs="+")
    ap.add_argument("--video", default=str(pathlib.Path.home() / ".cache/curling_score/videos/Go_JOSxJPsQ.mp4"))
    ap.add_argument("--side", default="weights/rcc2b.pt")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    doc = json.load(open(a.timeline))
    views = {n: view_from(doc["calibration"][n]) for n in ("left", "right")}
    end = next(e for e in doc["games"][0]["ends"] if e["number"] == a.end)
    dest, hog = views[hogtime.CAMERA_FOR[end["house"]]], views[hogtime.CAMERA_FOR[OTHER[end["house"]]]]
    for name, v in (("destination", dest), ("throwing", hog)):
        h = v.rect[3]
        print(f"{name} camera: rows 0-{h}, tee row {v.tee_row:.0f}, hog row {v.hog_row:.0f}; its last row is "
              f"{v.metres_at(h - 1):.2f} m from its tee (hog line {C.TEE_TO_HOGLINE_M:.2f}); "
              f"band_crop {band_crop(v)}; broom crop {broommodel.crop_rows(v)}")
    side = sidemodel._load(a.side)
    broom = broommodel.default_model()
    pose = spinmodel.default_model()
    print("side", a.side, "broom", weights_mod.broom_path(), "spin", weights_mod.spin_path())
    for n in a.rocks:
        s = end["shots"][n - 1]
        col, t_rel, t_tee = s["color"], s["t_release_s"], s["t_tee_s"]
        print(f"\n== end {a.end} rock {n} ({col}) release {t_rel} tee {t_tee} hog {s['t_hog_s']} far {s['t_far_s']}")
        # -- the broom, in the destination camera
        frames, times = longview.decode(a.video, dest.rect, t_tee - broomtime.WINDOW_S, t_tee, broomtime.FPS)
        per = broommodel.find(broom, frames, dest)
        samples = [(i, *dest.to_house(p.col, p.row), p.conf) for i, pads in enumerate(per) for p in pads]
        held = broomtime.pick_targets(samples, len(frames))
        print(f"  broom: {len(frames)} frames, pads per frame {[len(p) for p in per]}")
        for b in held:
            print(f"    held pad x {b.x_m:+.2f} y {b.y_m:+.2f} seen {b.seen:.1f} conf {b.confidence:.2f}")
        print(f"    timeline's: {s['target_broom']}")
        if a.out:
            import cv2
            out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
            k = len(frames) // 2
            img = longview.to_bgr(frames[k]).copy()
            for p in per[k]:
                cv2.rectangle(img, (int(p.x0), int(p.y0)), (int(p.x1), int(p.y1)), (0, 255, 0), 2)
                cv2.putText(img, f"{p.conf:.2f}", (int(p.x0), int(p.y0) - 4), 0, 0.6, (0, 255, 0), 2)
            cv2.imwrite(str(out / f"e{a.end}r{n}-broom.jpg"), img)
        # -- the hog crossing and what the line pass has to fit
        t0, t1 = t_rel + longview.WINDOW_S[0], t_rel + longview.WINDOW_S[1]
        got = sidemodel.find_crossing(side, a.video, hog, col, t0, t1)
        track = linetime.hog_track(got, hog)
        print(f"  hog: {got.key} t {got.t} ({got.reason}); {len(got.samples)} samples, relinked track {len(track)}")
        if track:
            yp = [p[3] for p in track]
            lo, hi = linetime.FIT_PAST_TEE_M
            print(f"    track runs {min(yp):.2f} to {max(yp):.2f} m past the throwing tee; "
                  f"{sum(lo <= y <= hi for y in yp)} samples in the line's window {lo:.1f}-{hi:.1f} m "
                  f"(needs {linetime.FIT_MIN_N} over {linetime.FIT_MIN_SPAN_M} m)")
            print(f"    fit_line -> {linetime.fit_line(track)}; final_fit -> {linetime.final_fit(track)}")
            for w in ((0.0, C.TEE_TO_HOGLINE_M), (3.0, C.TEE_TO_HOGLINE_M)):
                f = linetime.fit_line(track, w, 8, 1.5)
                print(f"    a line over {w[0]:.1f}-{w[1]:.1f} m: " + ("none" if f is None else
                      f"n {f.n} rms {f.rms * 100:.1f} cm slope {f.b:+.4f}"))
        # -- spin
        shot = SimpleNamespace(hog_crossing=got, t_hog_s=got.t, color=col)
        start = spintime.spin_start(shot, hog)
        print(f"  spin: start {None if not start else (round(start[0], 2), [round(v, 1) for v in start[1]])}")
        if start:
            t_ref = start[0]
            fr, ts = longview.decode(a.video, hog.rect, t_ref + spintime.WINDOW_S[0], t_ref + spintime.WINDOW_S[1],
                                     spintime.SPIN_FPS)
            lo_row = int(hog.hog_row) - spintime.ABOVE_HOG_ROWS
            boxes = sidemodel.detect_boxes(side, fr, ts, lo_row, fr.shape[1], col, imgsz=800, conf=0.25)
            tracked = spintime.follow(ts, boxes, start[1], hog, fr.shape[1])
            print(f"    rows read {lo_row}-{fr.shape[1]} ({fr.shape[1] - lo_row} rows, to "
                  f"{hog.metres_at(fr.shape[1] - 1):.2f} m; spin counts from {spintime.FROM_M} m); "
                  f"boxes in {sum(bool(b) for b in boxes)}/{len(boxes)} frames; followed {len(tracked)}")
            tr = spintime.track_spin(side, pose, a.video, hog, shot, decode=longview.decode,
                                     detect=sidemodel.detect_boxes, points=spinmodel.handle_points, start=start)
            print(f"    track_spin -> {None if tr is None else (len(tr.ts), 'samples')}")


if __name__ == "__main__":
    sys.exit(main())
