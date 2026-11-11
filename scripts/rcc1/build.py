#!/usr/bin/env python
"""rcc1: mine, pick, cut and pre-label 100 Rochester overhead frames for the hand review.

Rochester Curling Club plays red and blue stones (Go_JOSxJPsQ, 2026-11-04),
and overhead-3 has only ever seen red and yellow: it reads the reds at 0.93
and misses every blue. Blue is to be the yellow_stone class. The blue handle
(H 124-127, S 91-119) is the hue of the houses' purple paint (H 128-135,
S 20-80), so only saturation tells them apart; the pre-labels are overhead-3's
boxes on a blue-to-yellow copy of the same crop, which finds perhaps half the
blues. The rest are for the reviewer to add.

As dfw1 (`scripts/dallas/build_dfw1.py`), from what overhead-3 boxes every 2 s
on the swapped copy:

  empty  a house with no sure box
  play   a house with stones in it, the busiest and the most doubtful first
         (boxes between DOUBT_LO and SURE count double)

Each kind and panel is spread over the stream: equal-count runs, the strongest
frame of each. Reads the strip proxy `analyze` cached, so it decodes little.

    python scripts/rcc1/build.py --proxy ~/.cache/curling_score/proxies/Go_JOSxJPsQ.6x733x1908x342.mp4 \\
        --out out/rcc1 --manifest datasets/rcc1/manifest.json
    python scripts/rcc1/build.py --render-only --out out/rcc1 --manifest datasets/rcc1/manifest.json
"""

import argparse
import json
from collections import Counter
from pathlib import Path

SHARES = {("empty", "top"): 10, ("empty", "bottom"): 10, ("play", "top"): 40, ("play", "bottom"): 40}
MINE_CONF, PRELABEL_CONF, IMGSZ, EVERY_S = 0.05, 0.25, 448, 2.0
SURE, DOUBT_LO = 0.5, 0.1
# The blue handle on video, and what the copy turns it into.
BLUE_H, BLUE_SMIN, YELLOW_H, V_GAIN, S_GAIN = (118, 130), 88, 25, 1.8, 1.2
BOX_ALL = ("BLUE stones are the YELLOW class: box each blue stone as yellow (y), and every red as red (r). "
           "Box EVERY stone in the frame, including any partly hidden under a person, a broom or a foot, and "
           "any cut off at the panel's edge. Reject every box that is not a stone -- jackets, shoes, broom "
           "heads, the purple paint -- and fix any blue stone boxed as red.")


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


def panel_rects(proxy: Path):
    """The two panels inside the proxy, from the club's layout and the crop in the proxy's name."""
    from curling_score import clubs

    sx, sy, _w, _h = (int(v) for v in proxy.stem.split(".")[-1].split("x"))
    layout = clubs.CLUBS["rochester"].panel_layout
    return {name: (x - sx, y - sy, w, h) for name, (x, y, w, h) in (("top", layout.top), ("bottom", layout.bottom))}


def mine(a, model, rects):
    """overhead-3's boxes on the swapped copy of both panels, every EVERY_S."""
    import cv2

    cap = cv2.VideoCapture(str(a.proxy))
    fps = cap.get(cv2.CAP_PROP_FPS)
    step, i, out = int(round(EVERY_S * fps)), 0, []
    while True:
        if not cap.grab():
            break
        if i % step == 0:
            ok, frame = cap.retrieve()
            if not ok:
                break
            names = list(rects)
            crops = [blue_to_yellow(frame[y:y + h, x:x + w]) for x, y, w, h in (rects[n] for n in names)]
            for name, res in zip(names, model.predict(crops, conf=MINE_CONF, imgsz=IMGSZ, verbose=False)):
                out.append({"t": round(i / fps, 2), "frame": i, "panel": name, "boxes": [
                    {"cls": int(k), "conf": round(cf, 3)}
                    for k, cf in zip(res.boxes.cls.tolist(), res.boxes.conf.tolist())]})
            if len(out) % 1000 == 0:
                print(f"{i / fps:.0f} s, {len(out)} panel frames", flush=True)
        i += 1
    return out, fps


def kind_of(f):
    sure = [b for b in f["boxes"] if b["conf"] >= SURE]
    doubt = [b for b in f["boxes"] if DOUBT_LO <= b["conf"] < SURE]
    if not sure:
        return ("empty", -len(doubt)) if not doubt else (None, 0)
    return "play", len(sure) + 2 * len(doubt)


def pick(frames):
    pools = {k: [] for k in SHARES}
    for f in frames:
        k, score = kind_of(f)
        if k:
            pools[(k, f["panel"])].append((f["t"], score, f))
    chosen = []
    for (k, panel), n in SHARES.items():
        pool = sorted(pools[(k, panel)], key=lambda c: c[0])
        for i in range(n):
            run = pool[i * len(pool) // n:(i + 1) * len(pool) // n]
            if run:
                t, score, f = max(run, key=lambda c: c[1])
                chosen.append({"kind": k, "panel": panel, "t": t, "frame": f["frame"], "score": score,
                               "mined_sure": len([b for b in f["boxes"] if b["conf"] >= SURE]),
                               "candidates": len(pool)})
    return chosen


def stem_for(vid, panel, t):
    return f"{vid}_{panel[0]}_{t:09.2f}".replace(".", "_")


def note_for(f):
    house = "left (teal)" if f["panel"] == "top" else "right (purple)"
    if f["kind"] == "empty":
        why = f"the {house} house with no sure stone in it; overhead-3 drew {f['prelabels']} boxes"
    else:
        why = f"the {house} house in play; overhead-3 drew {f['prelabels']} boxes at {PRELABEL_CONF}+"
    return f"{why}. {BOX_ALL}"


def build(a):
    import cv2
    from ultralytics import YOLO

    out = a.out.expanduser()
    img_dir, lbl_dir = out / "set/images/train", out / "set/labels/train"
    for d in (img_dir, lbl_dir):
        d.mkdir(parents=True, exist_ok=True)
    model = YOLO(a.weights)
    rects = panel_rects(a.proxy)
    mined_path = out / "mined.json"
    if mined_path.exists():
        mined = json.loads(mined_path.read_text())
    else:
        frames, fps = mine(a, model, rects)
        mined = {"fps": fps, "frames": frames}
        mined_path.write_text(json.dumps(mined))
    print(f"{len(mined['frames'])} panel frames mined")
    cap = cv2.VideoCapture(str(a.proxy))
    frames_out = []
    for c in sorted(pick(mined["frames"]), key=lambda c: c["frame"]):
        cap.set(cv2.CAP_PROP_POS_FRAMES, c["frame"])
        ok, frame = cap.read()
        if not ok:
            print("no frame", c["t"])
            continue
        x, y, w, h = rects[c["panel"]]
        img = frame[y:y + h, x:x + w]
        stem = stem_for(a.video_id, c["panel"], c["t"])
        cv2.imwrite(str(img_dir / f"{stem}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 95])
        res = model.predict(blue_to_yellow(img), conf=PRELABEL_CONF, imgsz=IMGSZ, verbose=False)[0]
        rows = [f"{int(k)} {(x0 + x1) / 2 / w:.6f} {(y0 + y1) / 2 / h:.6f} {(x1 - x0) / w:.6f} {(y1 - y0) / h:.6f}"
                for k, (x0, y0, x1, y1) in zip(res.boxes.cls.tolist(), res.boxes.xyxy.tolist())]
        (lbl_dir / f"{stem}.txt").write_text("\n".join(rows) + ("\n" if rows else ""))
        frames_out.append({**c, "video": a.video_id, "stem": stem, "prelabels": len(rows)})
        print(f"{stem} {c['kind']}: {len(rows)} boxes", flush=True)
    manifest = {"what": a.title, "scope": a.scope,
                "images": f"the overhead panels of {a.proxy.name}, true colours",
                "prelabel": {"weights": Path(a.weights).name, "conf": PRELABEL_CONF, "imgsz": IMGSZ,
                             "on": "a blue-to-yellow copy of the same crop",
                             "classes": {0: "red_stone", 1: "yellow_stone (Rochester: blue)"}},
                "selection": {"shares": {f"{k}-{p}": n for (k, p), n in SHARES.items()}, "sure_conf": SURE,
                              "doubt_conf": DOUBT_LO, "mined_every_s": EVERY_S, "mined_conf": MINE_CONF},
                "by_kind": dict(Counter(f"{f['kind']}-{f['panel']}" for f in frames_out)), "frames": frames_out}
    a.manifest.parent.mkdir(parents=True, exist_ok=True)
    a.manifest.write_text(json.dumps(manifest, indent=1))
    print(f"{len(frames_out)} frames: {manifest['by_kind']}")
    render(out, manifest)


def render(out, manifest):
    """The review pages, from the set on disk and the manifest's notes. Labels
    are not touched, so a review in progress keeps every edit."""
    from curling_score.train import labels

    meta = {f["stem"]: labels.FrameMeta(note=note_for(f), url=f"https://youtu.be/{f['video']}?t={int(f['t'])}")
            for f in manifest["frames"]}
    frames = [f for seq in labels.load_split(out / "set", "train").values() for f in seq]
    page, _n = labels.render_clickable(frames, out / "review", title=manifest["what"],
                                       scope=manifest["scope"], per_page=200, meta=meta)
    print(f"{len(frames)} frames rendered: {page}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--proxy", type=Path, help="the strip proxy analyze cached for the video")
    ap.add_argument("--weights", default="weights/overhead-3.pt")
    ap.add_argument("--video-id", default="Go_JOSxJPsQ", help="names the frames and links them to YouTube")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--render-only", action="store_true")
    ap.add_argument("--scope", default="rcc1:train")
    ap.add_argument("--title", default="rcc1: Rochester's red and blue stones (Go_JOSxJPsQ)")
    a = ap.parse_args()
    if a.render_only:
        render(a.out.expanduser(), json.loads(a.manifest.read_text()))
        return
    build(a)


if __name__ == "__main__":
    main()
