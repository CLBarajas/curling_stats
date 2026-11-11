# rccbroom — broom heads on Rochester's end cameras

132 frames of `Go_JOSxJPsQ` (sheet A): for each of the 117 rocks the run `out/rcc-1104-fit` saw thrown, the
house-facing end camera half a second before the thrower crossed the tee; and a second frame, a full second
before, for each of the 15 rocks the run gave no broom. Rows `broommodel.crop_rows`, the full view width, as
the model is shown them. One class, `broom`; the labelling rule is `datasets/broom/README.md`'s: every broom
head resting on the ice, none held in the air.

- `scripts/rccbroom/build.py` cut the frames and pre-labelled them with `weights/broom4.pt` at 0.25.
- broom4, untuned, held a pad on **102 of 117 rocks** (87%). The 15 it left: 11 are a skip's own rocks (13 to
  16), when someone else holds the broom. On the one looked at (end 1 rock 13) that player's pad is dark grey
  and stands end on to the camera; the rest are not looked at yet.
- broom4 also boxes, at 0.31-0.35, the target broom as the overhead inset shows it, where the inset's corner
  cuts into the left view (col 310, row 810): a "pad" 0.44 m left of centre at the hog line. `pick_targets`
  ranks it below the real pad (further from the tee), so it has not been the target on any rock of this
  game, but nothing keeps it out.

**Not reviewed yet, and no model trained.** The set is pre-labels only. Once reviewed:

```bash
python scripts/rcc2/apply.py --set out/rccbroom1/set --manifest datasets/rccbroom/manifest.json \
    datasets/rccbroom/edits/label-edits-rccbroom-train-*.json
python scripts/rccbroom/fold.py --set out/rccbroom1/set --out out/rccbroom1/folds/a
DEVICE=mps scripts/rccbroom/run_rccbroom1a.sh
```

A model from it gets a new name in `weights/`, an allowlist line in `.gitignore`, its numbers and md5 here,
and is chosen with `CURLING_SCORE_BROOM_WEIGHTS` (a club profile names its stone models, not its broom model;
DFW's `bdfw1.pt` is chosen the same way, `deploy/dfw/docker-compose.yml`).

**Caveat:** every frame is from this one game on sheet A.
