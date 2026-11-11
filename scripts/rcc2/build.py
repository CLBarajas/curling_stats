#!/usr/bin/env python
"""rcc2: mine, pick, cut and pre-label 100 frames of Rochester's end cameras for the hand review.

Each of Rochester's two wide cameras sits behind its own hog line and looks
back at its own house, as Cincinnati's do (`geometry/endcam.py`), and its
overheads show the house only. So the end cameras have to give what the
overheads cannot: the guards, the stone arriving under its sweepers, and the
hog line. long-1 learned Granite's distant long cameras and red and yellow
stones; the first Rochester runs timed the far hog line on 1-4 rocks an end
(Go_JOSxJPsQ). Blue is the yellow_stone class, as in rcc1.

Frames are the rows `farfollow` reads, 80 above the tee to the bottom of the
view. Three kinds, for each camera:

  play      from cin3a's boxes on a blue-to-yellow copy every 2 s: stones in
            view, the busiest and most doubtful first, spread over the stream
  arriving  a throw the game run placed in this camera's house, 2 s or 4 s
            before the overhead saw it enter: the stone under its sweepers
  throwing  a throw delivered from this camera's end, 1 s before or 0.5 s
            after the release the run read: the stone in or just out of the hand

Pre-labels are cin3a's boxes at 0.25 on the blue-to-yellow copy; on four test
frames that found nearly every stone and called one blue red. The overhead
inset in each view's bottom corner is a picture of stones, not stones: nothing
in it is to be boxed.

    python scripts/rcc2/build.py --video ~/.cache/curling_score/videos/Go_JOSxJPsQ.mp4 \\
        --timeline out/rcc-1104-rcc1a/timeline.json --out out/rcc2 --manifest datasets/rcc2/manifest.json
    python scripts/rcc2/build.py --render-only --out out/rcc2 --manifest datasets/rcc2/manifest.json
"""

import argparse
import json
from collections import Counter
from pathlib import Path

SHARES = {"play": 20, "arriving": 15, "throwing": 15}  # for each camera
MINE_CONF, PRELABEL_CONF, IMGSZ, EVERY_S = 0.05, 0.25, 800, 2.0
SURE, DOUBT_LO = 0.5, 0.1
ROWS_ABOVE_TEE = 80
ARRIVING_BEFORE_ENTER_S = (2.0, 4.0)
THROWING_FROM_RELEASE_S = (-1.0, 0.5)
MIN_APART_S = 4.0
# The blue handle as the end cameras see it (H 104-120, S 82+), and the purple
# paint beside it (H 119-135, S under 60).
BLUE_H, BLUE_SMIN, YELLOW_H, V_GAIN, S_GAIN = (104, 130), 88, 25, 1.8, 1.2
# cin3a's boxes here, in metres of the lateral scale at their row.
BOX_M = (0.30, 0.22)
HOUSE_OF = {"left": "top", "right": "bottom"}  # the house each camera looks at
BOX_ALL = ("BLUE stones are the YELLOW class: box each blue stone as yellow (y), and every red as red (r). "
           "Box EVERY stone on the ice, including one under the thrower's hand, behind a broom or a sweeper's "
           "leg, parked at the side, or cut off by an edge. Do NOT box anything inside the small overhead "
           "picture in the bottom corner. Reject every box that is not a stone -- shoes, gloves, broom heads "
           "-- and fix any blue stone boxed as red.")


def blue_to_yellow(img):
    import cv2
    import numpy as np

    h, s, v = cv2.split(cv2.cvtColor(img, cv2.COLOR_BGR2HSV))
    m = (h >= BLUE_H[0]) & (h <= BLUE_H[1]) & (s >= BLUE_SMIN)
    h, s, v = h.copy(), s.copy(), v.copy()
    h[m] = YELLOW_H
    s[m] = np.clip(s[m].astype(np.float32) * S_GAIN, 0, 255).astype(np.uint8)
    v[m] = np.clip(v[m].astype(np.float32) * V_GAIN, 0, 255).astype(np.uint8)
    return cv2.cvtColor(cv2.merge([h, s, v]), cv2.COLOR_HSV2BGR)


def view_from(c):
    from curling_score.geometry.sideview import SideView

    return SideView(rect=tuple(c["rect"]), tee_row=c["tee_row"], hog_row=c["hog_row"], d_m=c["d_m"],
                    centre_col=c["centre_col"], lat_px_per_m_at_tee=c["lat_px_per_m_at_tee"],
                    centre_line=tuple(c["centre_line"]), end_camera=bool(c.get("end_camera")))


def crop_of(view):
    """(x, y, w, h) in the frame: the rows farfollow reads, to the bottom of the view."""
    x, y, w, h = view.rect
    top = max(0, int(view.tee_row) - ROWS_ABOVE_TEE)
    return x, y + top, w, h - top


def add_box(view, crop_top, w, h):
    """An added stone's normalised (w, h) at the crop's top and bottom edges (cin2's)."""
    _c, yh = view._map()
    per_m = [view.lat_px_per_m_at_tee * (row - yh) / (view.tee_row - yh) for row in (crop_top, crop_top + h)]
    return [[round(BOX_M[0] * s / w, 5), round(BOX_M[1] * s / h, 5)] for s in per_m]


def mine(video, model, crops):
    """cin3a's boxes on the swapped copy of both views, every EVERY_S."""
    import cv2

    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS)
    step, i, out = int(round(EVERY_S * fps)), 0, []
    names = list(crops)
    while cap.grab():
        if i % step == 0:
            ok, frame = cap.retrieve()
            if not ok:
                break
            imgs = [blue_to_yellow(frame[y:y + h, x:x + w]) for x, y, w, h in (crops[n] for n in names)]
            for name, res in zip(names, model.predict(imgs, conf=MINE_CONF, imgsz=IMGSZ, verbose=False)):
                out.append({"t": round(i / fps, 2), "view": name,
                            "conf": [round(c, 3) for c in res.boxes.conf.tolist()]})
            if len(out) % 1000 == 0:
                print(f"{i / fps:.0f} s, {len(out)} view frames", flush=True)
        i += 1
    return out, fps


def spread(pool, n, key=None):
    """n of the pool over the stream: equal-count runs, the strongest of each."""
    pool = sorted(pool, key=lambda c: c["t"])
    if len(pool) <= n:
        return pool
    runs = [pool[i * len(pool) // n:(i + 1) * len(pool) // n] for i in range(n)]
    return [max(r, key=key) if key else r[len(r) // 2] for r in runs]


def pick(mined, timeline):
    from curling_score.game import hogtime

    chosen = []
    throws = [(e["house"], s) for g in timeline["games"] for e in g["ends"] for s in e["shots"]]
    for view, house in HOUSE_OF.items():
        assert hogtime.CAMERA_FOR[house] == view
        play = []
        for f in mined:
            sure = sum(c >= SURE for c in f["conf"])
            doubt = sum(DOUBT_LO <= c < SURE for c in f["conf"])
            if f["view"] == view and sure:
                play.append({"kind": "play", "view": view, "t": f["t"], "score": sure + 2 * doubt})
        arriving = [{"kind": "arriving", "view": view, "score": 0,
                     "t": s["t_enter_s"] - ARRIVING_BEFORE_ENTER_S[i % 2]}
                    for i, (h, s) in enumerate(throws) if h == house and s.get("t_enter_s") is not None]
        throwing = [{"kind": "throwing", "view": view, "score": 0,
                     "t": s["t_release_s"] + THROWING_FROM_RELEASE_S[i % 2]}
                    for i, (h, s) in enumerate(throws) if h != house and s.get("t_release_s") is not None]
        got = spread(arriving, SHARES["arriving"]) + spread(throwing, SHARES["throwing"])
        # Play frames fill what the throws could not, and stay clear of them.
        play = [p for p in play if all(abs(p["t"] - g["t"]) >= MIN_APART_S for g in got)]
        got += spread(play, sum(SHARES.values()) - len(got), key=lambda c: c["score"])
        chosen += got
    return sorted(chosen, key=lambda c: c["t"])


def stem_for(vid, view, t):
    return f"{vid}_{view[0]}_{t:09.2f}".replace(".", "_")


def note_for(f):
    house = "left (teal) house" if f["view"] == "left" else "right (purple) house"
    why = {"play": f"the {house}'s camera with stones in view",
           "arriving": f"the {house}'s camera as a throw arrives",
           "throwing": f"the {house}'s camera as a throw is delivered from its end"}[f["kind"]]
    return f"{why}; cin3a drew {f['prelabels']} boxes at {PRELABEL_CONF}+. {BOX_ALL}"


def build(a):
    import cv2
    from ultralytics import YOLO

    out = a.out.expanduser()
    img_dir, lbl_dir = out / "set/images/train", out / "set/labels/train"
    for d in (img_dir, lbl_dir):
        d.mkdir(parents=True, exist_ok=True)
    timeline = json.loads(a.timeline.read_text())
    cal = {name: timeline["calibration"][name] for name in HOUSE_OF}
    views = {name: view_from(c) for name, c in cal.items()}
    crops = {name: crop_of(v) for name, v in views.items()}
    model = YOLO(a.weights)
    mined_path = out / "mined.json"
    if mined_path.exists():
        mined = json.loads(mined_path.read_text())
    else:
        frames, fps = mine(a.video, model, crops)
        mined = {"fps": fps, "frames": frames}
        mined_path.write_text(json.dumps(mined))
    print(f"{len(mined['frames'])} view frames mined")
    cap = cv2.VideoCapture(str(a.video))
    fps = mined["fps"]
    frames_out = []
    for c in pick(mined["frames"], timeline):
        i = int(round(c["t"] * fps))
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok, frame = cap.read()
        if not ok:
            print("no frame", c["t"])
            continue
        x, y, w, h = crops[c["view"]]
        img = frame[y:y + h, x:x + w]
        t = i / fps
        stem = stem_for(a.video_id, c["view"], t)
        cv2.imwrite(str(img_dir / f"{stem}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 95])
        # One box a stone: left to itself the model boxed a stone in both
        # colours on 13 of the first 100 frames, and two boxes drawn on top of
        # one another look like one to the reviewer.
        res = model.predict(blue_to_yellow(img), conf=PRELABEL_CONF, imgsz=IMGSZ, agnostic_nms=True,
                            verbose=False)[0]
        rows = [f"{int(k)} {(x0 + x1) / 2 / w:.6f} {(y0 + y1) / 2 / h:.6f} {(x1 - x0) / w:.6f} {(y1 - y0) / h:.6f}"
                for k, (x0, y0, x1, y1) in zip(res.boxes.cls.tolist(), res.boxes.xyxy.tolist())]
        (lbl_dir / f"{stem}.txt").write_text("\n".join(rows) + ("\n" if rows else ""))
        crop_top = y - views[c["view"]].rect[1]
        frames_out.append({**c, "t": round(t, 3), "frame": i, "video": a.video_id, "stem": stem,
                           "prelabels": len(rows), "crop_top": crop_top, "width": w, "height": h,
                           "add_box": add_box(views[c["view"]], crop_top, w, h)})
        print(f"{stem} {c['kind']}: {len(rows)} boxes", flush=True)
    manifest = {"what": a.title, "scope": a.scope, "views": cal,
                "images": f"each end camera of {a.video.name}, {ROWS_ABOVE_TEE} rows above the tee to the "
                          "bottom of the view, true colours",
                "prelabel": {"weights": Path(a.weights).name, "conf": PRELABEL_CONF, "imgsz": IMGSZ,
                             "on": "a blue-to-yellow copy of the same crop",
                             "classes": {0: "red_stone", 1: "yellow_stone (Rochester: blue)"}},
                "selection": {"shares_per_camera": SHARES, "sure_conf": SURE, "doubt_conf": DOUBT_LO,
                              "mined_every_s": EVERY_S, "mined_conf": MINE_CONF,
                              "timeline": str(a.timeline)},
                "by_kind": dict(Counter(f"{f['kind']}-{f['view']}" for f in frames_out)), "frames": frames_out}
    a.manifest.parent.mkdir(parents=True, exist_ok=True)
    a.manifest.write_text(json.dumps(manifest, indent=1))
    print(f"{len(frames_out)} frames: {manifest['by_kind']}")
    render(out, manifest)


def render(out, manifest):
    """The review pages, from the set on disk and the manifest's notes. Labels
    are not touched, so a review in progress keeps every edit."""
    from curling_score.train import labels

    meta = {f["stem"]: labels.FrameMeta(box=tuple(map(tuple, f["add_box"])), note=note_for(f),
                                        url=f"https://youtu.be/{f['video']}?t={int(f['t'])}")
            for f in manifest["frames"]}
    frames = [f for seq in labels.load_split(out / "set", "train").values() for f in seq]
    page, _n = labels.render_clickable(frames, out / "review", title=manifest["what"],
                                       scope=manifest["scope"], per_page=200, meta=meta,
                                       class_display={1: ("blue", "#2f6fdf")})
    print(f"{len(frames)} frames rendered: {page}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", type=Path, help="the full-resolution video")
    ap.add_argument("--timeline", type=Path, help="a game run's timeline, for the views and the throws")
    ap.add_argument("--weights", default="weights/cin3a.pt")
    ap.add_argument("--video-id", default="Go_JOSxJPsQ", help="names the frames and links them to YouTube")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--render-only", action="store_true")
    ap.add_argument("--scope", default="rcc2:train")
    ap.add_argument("--title", default="rcc2: Rochester's end cameras (Go_JOSxJPsQ)")
    a = ap.parse_args()
    if a.render_only:
        render(a.out.expanduser(), json.loads(a.manifest.read_text()))
        return
    build(a)


if __name__ == "__main__":
    main()
