# rcc1 — Rochester's overhead houses

100 overhead-panel frames from Rochester Curling Club's sheet A stream `Go_JOSxJPsQ` (Wed Comp, 2026-11-04,
1080p30), 50 a house. Rochester plays red and blue stones; overhead-3 reads the reds at 0.93 and misses every
blue. **Blue is the `yellow_stone` class.**

The blue handle (H 124-127, S 91-119) is the hue of the houses' purple paint (H 128-135, S 20-80), so only
saturation separates them.

- `scripts/rcc1/build.py`: overhead-3 at 0.05 on a blue-to-yellow copy of both panels every 2 s; 10 empty and 40
  in-play frames a house, spread over the stream (dfw1's rule). Pre-labels are overhead-3 at 0.25 on the same
  copy: 130 red and 219 "yellow" boxes, many of the yellows on bare purple paint.
- Review (`edits/`): two exports. The second is the whole review, all 100 frames, 62 rejects, 28 adds; the first
  is its first 84 frames. Apply the second alone.
- Reviewed set: 128 red and 187 blue boxes; 25 frames kept empty.
- `scripts/rcc1/make_fold.py`: the reviewed frames alone, every fifth by time to val (80 / 20). The base set's
  images are not in the repository, so unlike cin1 and dfw1 this is a tune of overhead-3's weights, not a retrain
  on its recipe.

| model | from | fold | red P / R | blue P / R | notes |
|---|---|---|---|---|---|
| overhead-3 | — | a (84 frames), val 16 | .73 / .89 | .15 / .04 | |
| rcc1a | overhead-3 | a, val 16 | 1.00 / 1.00 | .90 / .87 | first export only; superseded, not committed |
| **rcc1b** | overhead-3 | b (100 frames), val 20 | .96 / .98 | .87 / .95 | `weights/rcc1b.pt`, md5 38a47b2c97dd49eccaca10b1dab71632 |

rcc1b: `DEVICE=cpu FOLD=b NAME=rcc1b scripts/rcc1/run_rcc1a.sh` (93 epochs, best at 68). At the 448 px the
analysis runs it at, red recall is 1.00 and blue 0.97 on the same val frames.

**Caveat:** every frame, train and val, is from this one game on sheet A.
