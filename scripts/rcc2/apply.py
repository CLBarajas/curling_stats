#!/usr/bin/env python
"""rcc2: apply a review's exported edits to the set, sizing each added stone by its row.

An end camera's stones are about twice as wide at the bottom of the frame as
at the top, so an added box takes the size the manifest's ``add_box`` gives
for the row it was clicked on (`labels.apply_edits`, a pair of sizes); a
recoloured box keeps the size of the one it replaced. Frames stripped to
nothing stay as negatives; frames nobody ticked are dropped.

    python scripts/rcc2/apply.py --set out/rcc2/set --manifest datasets/rcc2/manifest.json \\
        datasets/rcc2/edits/label-edits-rcc2-train-*.json
"""

import argparse
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("edits", nargs="+", type=Path)
    ap.add_argument("--set", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--scope", help="the edits' scope, when not the manifest's (a second pass)")
    a = ap.parse_args()

    from curling_score.train import labels

    manifest = json.loads(a.manifest.read_text())
    sizes = {f["stem"]: tuple(map(tuple, f["add_box"])) for f in manifest["frames"] if f.get("add_box")}
    edits = labels.merge_edits(*(json.loads(p.read_text()) for p in a.edits))
    want = a.scope or manifest["scope"]
    if edits.scope and edits.scope != want:
        raise SystemExit(f"these edits are scoped {edits.scope!r}, not {want!r}")
    c = labels.apply_edits(a.set, "train", edits.reject, edits.add, keep_empty=True,
                           box_for=sizes.get, reviewed=edits.reviewed,
                           # A second pass shows only some frames: the rest stay as they are.
                           drop_unreviewed=not a.scope)
    print(c)
    print(f"{dedupe(a.set)} box(es) dropped: a second box of the same colour on one stone")


def dedupe(root, min_iou=0.5):
    """Drop a box lying on another of its own colour. Two colours on one stone
    are left for a person (`second_pass.py`)."""
    from curling_score.train import labels

    dropped = 0
    for lbl in sorted((root / "labels/train").glob("*.txt")):
        boxes, keep = labels._read_boxes(lbl), []
        for b in boxes:
            if any(k.cls == b.cls and _iou(k, b) >= min_iou for k in keep):
                dropped += 1
            else:
                keep.append(b)
        if len(keep) != len(boxes):
            labels._write_boxes(lbl, keep)
    return dropped


def _iou(a, b):
    x0, x1 = max(a.cx - a.w / 2, b.cx - b.w / 2), min(a.cx + a.w / 2, b.cx + b.w / 2)
    y0, y1 = max(a.cy - a.h / 2, b.cy - b.h / 2), min(a.cy + a.h / 2, b.cy + b.h / 2)
    inter = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    union = a.w * a.h + b.w * b.h - inter
    return inter / union if union else 0.0


if __name__ == "__main__":
    main()
