#!/usr/bin/env python
"""rcc2: a second look at the frames where a model trained on the review disagrees with it.

The first review of rcc2 left slips a model shows up at once: a blue stone
still boxed red, a stone boxed in both colours where a recolour's old box came
back, a box on a shirt's logo. On the 20 validation frames, 5 of rcc2a's 9
"errors" were the label's, not the model's. This renders only the frames where
the model and the labels differ -- a labelled stone the model has no box on, a
box of the other colour, a model box where no stone is labelled -- with a note
naming each difference by its box number, for the reviewer to settle. Most
differences are the model's and need nothing but the tick.

The page is rendered from the set as the first review left it, under its own
scope, so its export applies on top (`apply.py --scope`).

    python scripts/rcc2/second_pass.py --weights out/rcc2/runs/rcc2a-gpu/weights/best.pt \\
        --set out/rcc2/set --manifest datasets/rcc2/manifest.json --out out/rcc2/review/pass2
"""

import argparse
import json
from pathlib import Path

CONF, IMGSZ, MATCH_IOU = 0.25, 800, 0.3
SCOPE = "rcc2:pass2"
NAMES = ("red", "blue")


def iou(a, b):
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union else 0.0


def differences(frame, preds):
    """What the model makes of a frame's labels, as sentences. ``preds`` are
    (cls, x0, y0, x1, y1), normalised."""
    out, used = [], set()
    boxes = [(b.cls, b.cx - b.w / 2, b.cy - b.h / 2, b.cx + b.w / 2, b.cy + b.h / 2) for b in frame.boxes]
    for i, a in enumerate(boxes):
        for j, b in enumerate(boxes[:i]):
            if iou(a[1:], b[1:]) >= 0.5:
                out.append(f"boxes {j + 1} and {i + 1} are on the same stone")
    for i, g in enumerate(boxes, 1):
        best = max(((iou(g[1:], p[1:]), k) for k, p in enumerate(preds) if k not in used), default=(0, None))
        if best[0] < MATCH_IOU:
            out.append(f"the model sees no stone at box {i} ({NAMES[g[0]]})")
            continue
        used.add(best[1])
        if preds[best[1]][0] != g[0]:
            out.append(f"the model says box {i} ({NAMES[g[0]]}) is {NAMES[preds[best[1]][0]]}")
    for k, p in enumerate(preds):
        if k not in used and not any(iou(p[1:], g[1:]) >= MATCH_IOU for g in boxes):
            out.append(f"the model sees an unlabelled {NAMES[p[0]]} stone {(p[1] + p[3]) / 2:.0%} across, "
                       f"{(p[2] + p[4]) / 2:.0%} down")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", required=True)
    ap.add_argument("--set", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()

    import cv2
    from ultralytics import YOLO

    from curling_score.train import labels

    manifest = json.loads(a.manifest.read_text())
    by_stem = {f["stem"]: f for f in manifest["frames"]}
    model = YOLO(a.weights)
    show, meta = [], {}
    frames = [f for seq in labels.load_split(a.set, "train").values() for f in seq]
    for frame in frames:
        img = cv2.imread(str(frame.image))
        h, w = img.shape[:2]
        res = model.predict(img, conf=CONF, imgsz=IMGSZ, verbose=False)[0]
        preds = [(int(k), x0 / w, y0 / h, x1 / w, y1 / h)
                 for k, (x0, y0, x1, y1) in zip(res.boxes.cls.tolist(), res.boxes.xyxy.tolist())]
        diffs = differences(frame, preds)
        if not diffs:
            continue
        f = by_stem[frame.image.stem]
        show.append(frame)
        meta[frame.image.stem] = labels.FrameMeta(
            box=tuple(map(tuple, f["add_box"])), url=f"https://youtu.be/{f['video']}?t={int(f['t'])}",
            note="Check: " + "; ".join(diffs) + ". Fix the label if it is wrong; if the model is wrong, just tick done.")
    page, n = labels.render_clickable(show, a.out, title=f"rcc2, second pass: {len(show)} frames a model questions",
                                      scope=SCOPE, per_page=200, meta=meta,
                                      class_display={1: ("blue", "#2f6fdf")})
    print(f"{len(show)} of {len(frames)} frames rendered: {page}")


if __name__ == "__main__":
    main()
