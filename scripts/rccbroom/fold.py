#!/usr/bin/env python
"""rccbroom: the reviewed set as a training fold, every fifth frame by time to val.

Run after `scripts/rcc2/apply.py` has applied the review to the set (it drops
the frames nobody ticked and keeps a reviewed frame with no pad as a negative).

    python scripts/rccbroom/fold.py --set out/rccbroom1/set --out out/rccbroom1/folds/a
"""

import argparse
import shutil
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--val-every", type=int, default=5)
    a = ap.parse_args()
    images = sorted((a.set / "images/train").glob("*.jpg"), key=lambda p: p.stem.split("_", 2)[-1][2:])
    n = {"train": 0, "val": 0}
    for i, img in enumerate(images):
        split = "val" if i % a.val_every == a.val_every - 1 else "train"
        for kind, src in (("images", img), ("labels", a.set / "labels/train" / f"{img.stem}.txt")):
            dst = a.out / kind / split
            dst.mkdir(parents=True, exist_ok=True)
            if src.exists():
                shutil.copyfile(src, dst / src.name)
            else:
                (dst / src.name).write_text("")
        n[split] += 1
    (a.out / "data.yaml").write_text(
        f"path: {a.out.resolve()}\ntrain: images/train\nval: images/val\nnames:\n  0: broom\n")
    print(n, a.out / "data.yaml")


if __name__ == "__main__":
    main()
