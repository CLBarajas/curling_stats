# rcc2 — Rochester's end cameras

100 frames from the two wide cameras of `Go_JOSxJPsQ` (sheet A), 50 a camera. Each sits behind its own hog line
and looks back at its own house, as Cincinnati's do; the overheads show the house only, so these cameras have to
give the guards, the stone arriving under its sweepers, and the hog line. Frames run from 80 rows above the tee
to the bottom of the view, the rows `farfollow` reads. **Blue is the `yellow_stone` class.**

- `scripts/rcc2/build.py`, for each camera: 20 `play` frames (cin3a's boxes on a blue-to-yellow copy every 2 s,
  busiest first, spread over the stream), 15 `arriving` (2 s or 4 s before the overhead saw a throw enter) and 15
  `throwing` (around the release), from the run `out/rcc-1104-rcc1a`.
- Pre-labels: cin3a at 0.25 on the blue-to-yellow copy, 228 red and 180 "yellow". **It boxed one stone in both
  colours on 13 frames**, one box on top of the other, which the review page shows as one box and rejects as one;
  the builder now asks for class-agnostic NMS.
- Review, first pass (`edits/label-edits-rcc2-train-*`): all 100 frames, 66 rejects, 76 adds, 40 of them
  recolours. `scripts/rcc2/apply.py` sizes an added box by its row and drops a second box of the same colour.
- Second pass (`scripts/rcc2/second_pass.py`, `edits/label-edits-rcc2-pass2-*`): the 28 frames where a model
  trained on the first pass disagreed with it; 11 rejects, 7 adds. Applied on top with `apply.py --scope
  rcc2:pass2`.
- Four stones still boxed in both colours after it (frames at 4706.70, 4898.89, 6048.04 and 6990.98 s) were
  settled by hand from the handle's colour, all blue. The pair at 1020.49 s is two stones.
- Reviewed set: 187 red and 206 blue boxes; 21 frames kept empty. Every fifth frame by time to val (80 / 20).

| model | from | labels | red P / R | blue P / R | notes |
|---|---|---|---|---|---|
| long-1 | — | cleaned, val 20 | .47 / .87 | .52 / .23 | Granite's; what the first runs used |
| cin3a | — | cleaned, val 20 | .41 / .87 | .42 / .57 | |
| rcc2a | cin3a | first pass | 1.00 / .84 | .94 / .81 | superseded, not committed |
| **rcc2b** | cin3a | both passes | 1.00 / .92 | .94 / .93 | `weights/rcc2b.pt`, md5 d60dade17c2997a2cacd60faf1ba4b91 |

rcc2b was trained on an Apple GPU (`device=mps`, 6 minutes), `scripts/rcc2/run_rcc2a.sh`'s recipe on fold `b`:
`yolo detect train model=weights/cin3a.pt data=out/rcc2/folds/b/data.yaml imgsz=800 epochs=100 patience=25
batch=8 seed=0 mosaic=1.0 close_mosaic=10 scale=0.4 degrees=0.0 fliplr=0.5 flipud=0.0 hsv_h=0.015 hsv_s=0.6
hsv_v=0.4`. Not reproducible to the bit: two MPS operations have no deterministic implementation.

**Caveat:** every frame, train and val, is from this one game on sheet A.
