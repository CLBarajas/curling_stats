#!/usr/bin/env python3
"""A fold of the reviewed rcc1 frames alone: every fifth by time is validation.

Unlike cin1 and dfw1, whose folds are the production model's training set plus
the club's 100 frames, this has only Rochester's: the base set's images are not
in the repository. rcc1a is therefore a tune of overhead-3's weights, not a
retrain on overhead-3's recipe. Symlinks only; stdlib only.

    python3 scripts/rcc1/make_fold.py --set out/rcc1/set --out out/rcc1/folds/a
"""

import argparse
from pathlib import Path

VAL_EVERY = 5


def link(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.is_symlink() or dst.exists():
        dst.unlink()
    dst.symlink_to(src.resolve())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    # By time, whichever house: the stem ends _<panel>_<seconds>_<hundredths>.
    imgs = sorted((a.set / "images/train").glob("*.jpg"), key=lambda p: p.stem.split("_")[-2:])
    n = {"train": 0, "val": 0}
    for i, img in enumerate(imgs):
        split = "val" if i % VAL_EVERY == VAL_EVERY - 1 else "train"
        link(img, a.out / f"images/{split}" / img.name)
        lbl = a.set / "labels/train" / f"{img.stem}.txt"
        dst = a.out / f"labels/{split}" / f"{img.stem}.txt"
        if lbl.exists():
            link(lbl, dst)
        else:  # a confirmed-empty frame: a background image
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text("")
        n[split] += 1
    (a.out / "data.yaml").write_text(f"path: {a.out.resolve()}\ntrain: images/train\nval: images/val\n"
                                     "names:\n  0: red_stone\n  1: yellow_stone\n")
    print(n)


if __name__ == "__main__":
    main()
