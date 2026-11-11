#!/usr/bin/env python
"""rccbroom: cut and pre-label the broom frames of a Rochester game for the hand review.

broom4 learned Granite's long cameras, a hundred feet from the house. On
Rochester's end cameras, twenty feet above it, it still held a pad on 102 of
Go_JOSxJPsQ's 117 rocks; the 15 it left were nearly all one team's last two
rocks of an end, called by a player whose pad is dark grey and seen end on.

One frame a rock, from the camera facing the house played to, half a second
before the thrower crossed the tee -- the middle of the second `broomtime`
reads -- and a second one, a full second before, for each rock the run gave
no broom. The crop is `broommodel.crop_rows`, the full width of the view, as
the model is shown it. Pre-labels are broom4's boxes at 0.25, class 0.

    python scripts/rccbroom/build.py --video ~/.cache/curling_score/videos/Go_JOSxJPsQ.mp4 \\
        --timeline out/rcc-1104-fit/timeline.json --out out/rccbroom1 --manifest datasets/rccbroom/manifest.json
    python scripts/rccbroom/build.py --render-only --out out/rccbroom1 --manifest datasets/rccbroom/manifest.json
"""

import argparse
import json
from collections import Counter
from pathlib import Path

PRELABEL_CONF, IMGSZ = 0.25, 800
BEFORE_TEE_S, AGAIN_BEFORE_TEE_S = 0.5, 1.0
# A pad lying along the sheet, in metres of the lateral scale at its row.
BOX_M = (0.12, 0.30)
BOX_ALL = ("Box EVERY broom head resting on the ice: the one held as the target and anyone else's -- a sweeper "
           "waiting at the side, the other skip behind the house. A broom held in the air is NOT boxed. "
           "Reject every box that is not a pad on the ice (a shoe, a stone's handle, the hack), and anything "
           "inside the small overhead picture in the bottom corner. Every box is the one class: press r to add.")


def view_from(c):
    from curling_score.geometry.sideview import SideView

    return SideView(rect=tuple(c["rect"]), tee_row=c["tee_row"], hog_row=c["hog_row"], d_m=c["d_m"],
                    centre_col=c["centre_col"], lat_px_per_m_at_tee=c["lat_px_per_m_at_tee"],
                    centre_line=tuple(c["centre_line"]), end_camera=bool(c.get("end_camera")))


def add_box(view, crop_top, w, h):
    """An added pad's normalised (w, h) at the crop's top and bottom edges."""
    _c, yh = view._map()
    per_m = [view.lat_px_per_m_at_tee * (row - yh) / (view.tee_row - yh) for row in (crop_top, crop_top + h)]
    return [[round(BOX_M[0] * s / w, 5), round(BOX_M[1] * s / h, 5)] for s in per_m]


def pick(timeline):
    """One frame a rock seen thrown, two for a rock with no broom."""
    from curling_score.game import hogtime

    out = []
    for g in timeline["games"]:
        for e in g["ends"]:
            for s in e["shots"]:
                if s.get("missing") or s.get("t_tee_s") is None:
                    continue
                base = {"view": hogtime.CAMERA_FOR[e["house"]], "end": e["number"], "rock": s["number"]}
                held = s.get("target_broom") is not None
                out.append({**base, "kind": "held" if held else "none", "t": s["t_tee_s"] - BEFORE_TEE_S})
                if not held:
                    out.append({**base, "kind": "none", "t": s["t_tee_s"] - AGAIN_BEFORE_TEE_S})
    return out


def stem_for(vid, view, t):
    return f"{vid}_{view[0]}_{t:09.2f}".replace(".", "_")


def note_for(f):
    run = "the run held a pad here" if f["kind"] == "held" else "the run found NO held pad for this rock"
    return f"end {f['end']} rock {f['rock']}: {run}; broom4 drew {f['prelabels']} boxes at {PRELABEL_CONF}+. {BOX_ALL}"


def build(a):
    import cv2
    from ultralytics import YOLO

    from curling_score.detect import broommodel

    out = a.out.expanduser()
    img_dir, lbl_dir = out / "set/images/train", out / "set/labels/train"
    for d in (img_dir, lbl_dir):
        d.mkdir(parents=True, exist_ok=True)
    timeline = json.loads(a.timeline.read_text())
    cal = {name: timeline["calibration"][name] for name in ("left", "right")}
    views = {name: view_from(c) for name, c in cal.items()}
    model = YOLO(a.weights)
    cap = cv2.VideoCapture(str(a.video))
    fps = cap.get(cv2.CAP_PROP_FPS)
    frames_out = []
    for c in pick(timeline):
        i = int(round(c["t"] * fps))
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok, frame = cap.read()
        if not ok:
            print("no frame", c["t"])
            continue
        view = views[c["view"]]
        x, y, w, _h = view.rect
        top, bot = broommodel.crop_rows(view)
        img = frame[y + top:y + bot, x:x + w]
        h = bot - top
        t = i / fps
        stem = stem_for(a.video_id, c["view"], t)
        cv2.imwrite(str(img_dir / f"{stem}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 95])
        res = model.predict(img, conf=PRELABEL_CONF, imgsz=IMGSZ, agnostic_nms=True, verbose=False)[0]
        rows = [f"0 {(x0 + x1) / 2 / w:.6f} {(y0 + y1) / 2 / h:.6f} {(x1 - x0) / w:.6f} {(y1 - y0) / h:.6f}"
                for x0, y0, x1, y1 in res.boxes.xyxy.tolist()]
        (lbl_dir / f"{stem}.txt").write_text("\n".join(rows) + ("\n" if rows else ""))
        frames_out.append({**c, "t": round(t, 3), "frame": i, "video": a.video_id, "stem": stem,
                           "prelabels": len(rows), "crop_top": top, "width": w, "height": h,
                           "add_box": add_box(view, top, w, h)})
        print(f"{stem} e{c['end']} r{c['rock']} {c['kind']}: {len(rows)} boxes", flush=True)
    manifest = {"what": a.title, "scope": a.scope, "views": cal,
                "images": f"the house-facing end camera of {a.video.name} before each rock's tee crossing, "
                          "rows broommodel.crop_rows, full view width",
                "prelabel": {"weights": Path(a.weights).name, "conf": PRELABEL_CONF, "imgsz": IMGSZ,
                             "classes": {0: "broom"}},
                "selection": {"before_tee_s": BEFORE_TEE_S, "again_before_tee_s": AGAIN_BEFORE_TEE_S,
                              "timeline": str(a.timeline)},
                "by_kind": dict(Counter(f"{f['kind']}-{f['view']}" for f in frames_out)), "frames": frames_out}
    a.manifest.parent.mkdir(parents=True, exist_ok=True)
    a.manifest.write_text(json.dumps(manifest, indent=1))
    print(f"{len(frames_out)} frames: {manifest['by_kind']}")
    render(out, manifest)


def render(out, manifest):
    """The review page, from the set on disk and the manifest's notes. Labels
    are not touched, so a review in progress keeps every edit."""
    from curling_score.train import labels

    meta = {f["stem"]: labels.FrameMeta(box=tuple(map(tuple, f["add_box"])), note=note_for(f),
                                        url=f"https://youtu.be/{f['video']}?t={int(f['t'])}")
            for f in manifest["frames"]}
    frames = [f for seq in labels.load_split(out / "set", "train").values() for f in seq]
    page, _n = labels.render_clickable(frames, out / "review", title=manifest["what"],
                                       scope=manifest["scope"], per_page=200, meta=meta,
                                       class_display={0: ("broom", "#18a058")})
    print(f"{len(frames)} frames rendered: {page}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", type=Path, help="the full-resolution video")
    ap.add_argument("--timeline", type=Path, help="a game run's timeline, for the views and the tee crossings")
    ap.add_argument("--weights", default="weights/broom4.pt")
    ap.add_argument("--video-id", default="Go_JOSxJPsQ", help="names the frames and links them to YouTube")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--render-only", action="store_true")
    ap.add_argument("--scope", default="rccbroom:train")
    ap.add_argument("--title", default="rccbroom: brooms on Rochester's end cameras (Go_JOSxJPsQ)")
    a = ap.parse_args()
    if a.render_only:
        render(a.out.expanduser(), json.loads(a.manifest.read_text()))
        return
    build(a)


if __name__ == "__main__":
    main()
