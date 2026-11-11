# rcc-lines — why Rochester's rocks had no line, broom figure or spin, and what they can have

Go_JOSxJPsQ (sheet A), the run `out/rcc-1104-fit`: every end logged `lines 0/N` and `spin 0/N`, and the viewer
said "The hog-line camera lost this rock" on every shot. Looked into 2026-11-11 on end 1 (16 rocks, 5:40-20:10)
with `scripts/rcc-lines/trace.py`, which runs each read's own functions on one rock and prints where it stops,
then on the whole game with `scripts/rcc-lines/lines.py` and `stats.py`. "Checked" below means run on the video
or looked at on a frame; "inferred" means reasoned from those.

## The short answer

| read | why it was empty | kind | now |
|---|---|---|---|
| target broom | it was not: broom4 held a pad on 102 of 117 rocks | model, for the other 15 | review set built, `datasets/rccbroom` |
| line | the pass fits the rock 0-12 ft **past** the hog line; these cameras stop 1 ft past it | camera position, and code | a line of what the camera does see: the delivery, where it crossed the hog line, the way in at the far end. No "Final" figure, ever |
| slide and release lines | they hang off the line, and off a release read by a model that does not fit these cameras | code, then model | the read is switched off here until a model is trained on Rochester marks |
| spin | read from 8 m past the tee on, on a camera that ends at 6.7 m | camera position | not from the thrower's camera. Possible, late in the rock's travel, from the far end's: not built |

Nothing was gated on stone colour, and the cameras' roles were not confused: `hogtime.CAMERA_FOR` names each
end camera for the house it looks at, so "the camera that times the throwing hog line" is the one above that
line looking back at the thrower, and "the camera facing the house" is the one above the far hog line. Both
are right. What differs from Granite is how far each sees.

## What each camera sees (checked)

Both views are 838 rows. The tee is on row 386-391 and the hog line on row 803-806; the last row is 6.68-6.70 m
from the tee, 0.28-0.30 m past the hog line (`SideView.metres_at`). So:

- The camera above the **throwing** hog line has the stone in the hack (3 m behind the tee), the whole slide
  coming at it, and the hog line. It never sees the rock in free flight.
- The camera above the **far** hog line has the rock from that line in: its last 6.4 m, the house, and the
  skip with the broom in the second before the throw.
- The 21.9 m between the hog lines is on neither camera, nor on the overheads, which show the houses only.

Granite's long camera sits behind the far house and sees the rock come at it the length of the sheet, which
is where the line (6.4-10 m past the throwing tee), the 9 ft "Final" window and the spin (8 m on) are read.

The fitted geometry holds: a grid drawn from each view's calibration lies on the hack, the back line, the
rings and the sideline on both cameras; a stone's box is 0.92-0.96 of the width the lateral scale predicts on
every row from the tee to the hog line (one delivery, 13 rows sampled); and on the three red rocks the
throwing end's overhead also saw (12, 14, 16) the two cameras put the stone within 2 cm of each other across
the sheet at the tee, with slide slopes of 0.068 / 0.072, 0.070 / 0.071 and 0.032 / 0.046.

## Per-rock traces, end 1 (checked: `trace.py`, before any change)

Rows of the throwing camera's track are metres past the throwing tee. The line pass asked for 15 samples
spanning 2.5 m between 6.4 and 10.0 m.

| rock | broom (x, y) m | hog crossing | track | in 6.4-10 m | line | spin |
|---|---|---|---|---|---|---|
| 1 blue | +1.45, +0.05, conf .88 | timed | 0.33-6.57 m, 95 samples | 10, all one row | refused: `fit_line` None | seed on the last row; 1 box in 101 frames, none followed |
| 2 red | -0.50, +1.53, .89 | timed | 0.54-6.57, 80 | 8 | refused | same |
| 3 blue | -1.42, +1.06, .89 | refused, "never reached" (lost at 5.5 m) | 0.68-5.50, 61 | 0 | refused | no start |
| 5 blue | +0.53, +1.61, .91 | timed | 1.00-6.57, 67 | 9 | refused | same as 1 |
| 7 blue | +0.26, +0.03, .89 | timed | 0.88-6.57, 70 | 8 | refused | 0 boxes |
| 9 blue | +1.30, +0.03, .88 | refused, "speed 0.99 m/s" | 0.22-6.57, 100 | 9 | refused | 2 boxes, none followed |
| 12 red | +1.38, -0.03, .49 | timed | 0.20-6.57, 100 | 10 | refused | 1 box |
| 13 blue | **none**: 0 pads in 11 frames | timed | 0.29-6.57, 99 | 10 | not tried: no broom | 0 boxes |
| 15 blue | **none** | refused, "speed 1.07 m/s" | 0.19-6.57, 102 | 10 | not tried | 0 boxes |
| 16 red | +1.18, -0.01, .89 | timed | 0.05-6.57, 109 | 11 | refused | 7 boxes, none followed |

- **Line.** Every rock with a broom reached `linetime.fit_line` and was refused there. The 8-11 samples "in
  the window" are not sightings of the rock past the hog line: they are boxes pinned to the frame's last row
  while the stone slides out under the camera, all at 6.57 m. The band the side model reads
  (`sideview.band_crop`) runs 3 m and 60 rows past the hog line, to row 1336-1357 of an 838-row view, so the
  rule that drops a box cut by the band's edge never fired.
- **Broom.** On the frame looked at for rock 2 the box is on the skip's pad. Rock 13's frame shows why it has
  none: the player holding the broom there stands it end on, a dark grey pad about 12 px wide, and broom4 draws
  nothing at 0.25. broom4 also boxes the target broom as the overhead inset shows it, at 0.31-0.35, where the
  inset's corner cuts into the left view; it has not been picked as a target (see `datasets/rccbroom`).
- **Spin.** The read starts half a second after the hog crossing in the rows from 40 above the hog line down,
  76 rows here, and counts only from 8 m past the tee. The rock has left the view before it starts.

## What was changed (branch `rcc-lines`)

1. `linetime.band_edge`: a box whose foot is on the view's last rows is dropped, as one on the band's is.
2. `linetime.pass_fit`: on an end camera the pass's own line is the rock's last 3 m to the hog line (15
   samples over 2 m). On end 1 it fitted to 0.1-0.6 cm rms on 9 of the 10 rocks traced (rock 2: 4.7 cm).
3. An end-camera line has **no final line** (`final_refused`, which the timeline and the viewer already
   carry: "too few sightings past the hog line"). It does say where the rock crossed the hog line
   (`at_hog.x`), read off its own line, which runs across it, and how far that was from the start-to-broom
   line (`at_hog.offset_m`). Nothing is extended to the broom.
4. `linetime.find_path_end`: the way in at the far end, from the camera above the far hog line, in one band
   as `farfollow` reads it, following the first stone to come in at the view's edge where none was parked
   (`farfollow.sightings`). Nothing ties it to the slide's line; 22 m lie between.
5. The start in front of the hack and the 30 fps delivery path need no change: the hack is in view.
6. `spintime.time_spins` returns at once on an end camera instead of decoding ten seconds a rock for nothing.
7. `releasetime.model_fits`: the release read does not run on an end camera unless a model is named for it
   (`CURLING_SCORE_RELEASE_WEIGHTS`). See below.

Tests are beside Will's: `tests/test_linetime.py` (`TestEndCameraFit`, `TestFindPathEnd`,
`TestTimeLinesOnEndCameras`), `tests/test_spintime.py`, `tests/test_releasetime.py`.

## What the changed pass reads

`scripts/rcc-lines/lines.py` rebuilds each rock's shot from the finished timeline (release, broom, rest) and
runs the hog, line, release and aim passes on the video, so no game run was needed. End 1, the same rocks as
above (x is metres to the thrower's right, y metres from the far tee):

| rock | line | start in front of the hack | delivery path | at the hog line | way in at the far end |
|---|---|---|---|---|---|
| 1 blue | yes | -0.07 | 145 points, 3.2 m behind the tee to the hog line | +0.35 | 9 points, +0.46 at 6.3 m to -0.02 at 1.4 m |
| 2 red | yes | -0.14 | 122 | -0.28 | 10 points, -0.25 at 6.4 m to -1.11 at 0.9 m (a hit and roll; the overhead rests it at -1.12) |
| 3 blue | yes | -0.14 | 119, to 5.5 m | -0.66 | none: it never reached the house (flashed) |
| 5 blue | yes | +0.13 | 117 | +0.23 | 7 points |
| 7 blue | yes | +0.13 | 115 | +0.16 | 11 points |
| 9 blue | yes | -0.04 | 143 | +0.47 | none found |
| 12 red | yes | -0.01 | 148 | +0.45 | 3 points, and on the wrong stone: it starts at -0.13 where the rock came in near +1 |
| 13, 15 blue | no: no broom | | | | |
| 16 red | yes | -0.06 | 163 | +0.57 | 12 points, +1.01 at 6.4 m to +0.49 at 0.2 m; the overhead has it resting at +0.52 |

End 1 in all: 13 of 16 (two with no broom; rock 6's track gave no fit). Where the far camera's path ends in
the house it is within 1-10 cm of the overhead's resting stone across the sheet on the seven rocks compared (1, 2, 4, 7,
11, 14, 16).

The whole game, the same way (`out/rcc-lines/*.json`, not committed):

- **97 lines on the 102 rocks that had a broom** (the run saw 117 rocks thrown). The five refused gave no fit
  over the last 3 m; why was not looked at.
- All 97 have the start in front of the hack and a delivery path that begins there (median first point 3.1 m
  behind the tee).
- 67 have a way in at the far end of two points or more. The follower takes the first stone to come in at
  the view's edge; rocks that never reach the far hog line have none, and it has been seen to take the wrong
  stone (end 1 rock 12). It wants a look rock by rock before it is trusted.
- Not run through `curling-score analyze`: that needs the GPU. The passes are the ones it calls, on shots
  rebuilt from its timeline.

## The release read does not transfer (checked)

`release1.pt` was run on the CPU along end 1's new delivery paths. It gave 13 releases, 0.8 to 5.8 m past the
tee. Frames 0.4 s before, at and 0.4 s after the read were looked at for rocks 11, 12 and 16: the hand is on
the handle in all nine. These throwers let go within a metre or two of the hog line. A wrong release moves
the slide and release lines by whole feet (rock 4: slide +33 cm, release line -24 cm, from a "release" 1 m
past the tee), so the read is off on end cameras until a model is trained on marks made here.

Late releases also bound what a release line can be at Rochester whatever the model: it is fitted over 9 ft
past the release and needs 2 m of it, and the camera's view ends 0.3 m past the hog line. A rock let go
inside the last 2 m gets a slide line and no release line.

## Is the slide's line the rock's line? (inferred, and not settled)

An end-camera line could still be extended to the broom, as Granite's final line is. It was not, because of
what the whole game says when it is (`scripts/rcc-lines/stats.py`; 97 rocks with a broom and a start):

- The slide's slope over its last 3 m is **1.53 times** the slope of the line from the stone's start to the
  broom, on both cameras (1.52 and 1.58), with a correlation of 0.97. The stone crosses the near hog line at
  0.40 of the broom's distance from the centre line where that line is at 0.25. Extended to the broom the
  slide's line misses it by a median 44 cm, the wrong way round for an error: the further out the broom, the
  further outside it.
- The positions behind that are sound as far as they can be checked: the overhead agrees to 2 cm at the tee
  (above), and on end 1 rock 16 the stone at the hog line is two of its own widths from the painted centre
  line on the frame, 0.57 m, where the line to its broom is at 0.25-0.30 m.
- But the rocks do not go where the slide points. For the 17 takeouts (hog to hog under 10.5 s, so little
  curl before the far hog line) the far camera has the rock coming in within a median 12 cm of the
  start-to-broom line, and 25 cm from the slide's line extended. Over all 69 rocks seen at both ends: 22 cm
  against 65 cm.

So either these throwers do slide half as wide again as the broom asks and the rock leaves the hand on a
shallower line than the slide's, or something stretches the slide across the sheet that none of the checks
above reaches. The cameras cannot say which: the release and the first 22 m of free travel are on neither.
Until that is understood, a figure that extends the slide to the broom would tell a thrower who made the shot
that he was a foot and a half wide. This is the first question for someone who curls there (below).

## What a curler would get

- **Now, with this branch and no new model:** on each rock with a broom, the sheet drawing (the hack-to-broom
  line, the rock's track to the hog line, its way in from the far hog line), the delivery chart (the rock
  from the hack to the hog line, every frame), which hack, and Weight as before. The Slide, Release, Final,
  At the hog line and Curl figures stay dashes, with true reasons ("no release read", "too few sightings past
  the hog line").
- **With a small viewer change** (not made; it is Will's call what a figure means): "At the hog line", how
  far off the hack-to-broom line the rock crossed the near hog line. It is the best-measured thing these
  cameras have, under the lens, with nothing extended. The timeline already carries it.
- **With a release model trained here:** Slide, and Release for early releasers.
- **With the broom set reviewed and a model trained:** the 13% of rocks with no broom, mostly the skips' own.
- **Not from these cameras:** the Final line (the rock's free line past the hog line) and so the miss at the
  broom as Granite's chart means it; the curl measured from that line; spin as thrown.
- **Spin, late:** the far end's camera has the rock for its last 6.4 m, and `spin1.pt` as it stands finds a
  handle on it (confidence 0.5 or more on every one of 91-106 frames of four rocks; the points looked right
  on the six crops looked at where no sweeper stood over the stone; one blue rock's grip swung through a full
  cycle in about 6.5 s). It would be a rate near the end of the rock's travel, on rocks slow enough to be in
  view for a third of a turn, with sweepers in front of the lens for much of it. Not built; say if it is
  wanted.

## Seen on the way, not changed

- `hogtime` refuses slow draws for speed here (end 1 rocks 9 and 15: 0.99 and 1.07 m/s against a 1.2 floor),
  so they have no hog time and no split. The speed is over the whole track, which on these cameras begins at
  the tee with the stone still being pushed, and ends with the boxes pinned to the last row. Another session
  has the hog timing.
- broom4's box on the overhead inset, above.
- A club profile names its stone models and not its broom or release model; both go by environment variable.

## Needed from Chris

1. **Does it look right to you?** End 1 rock 16 (19:40-19:45 in the video, red, the skip's last): the broom
   is about 4 ft right of centre, and the stone crosses the near hog line about 2 ft right of centre, twice
   where the line to that broom is. Every thrower in the game reads the same way, in proportion. Do players
   at the club slide outside the broom like that, or is the read wrong? One rock thrown with a marker on the
   hack-to-broom line at the near hog line would settle it.
2. **A full run on the GPU**, to see the lines in the viewer and to give the release marker its delivery
   paths (25 min):
   `curling-score -v analyze "https://www.youtube.com/watch?v=Go_JOSxJPsQ" --club rochester --device mps --out out/rcc-lines-run`
   from a checkout of `rcc-lines` (or with `PYTHONPATH=../curling_stats-lines/src` from the main one).
3. **The broom review** (132 frames, about 15 minutes): serve `out/rccbroom1/review/` as the rcc2 pages
   were served, box every pad on the ice, export, and save the file under `datasets/rccbroom/edits/`. Then the
   three commands in `datasets/rccbroom/README.md`; the training is `DEVICE=mps`, about 6 minutes.
4. **Release marks, if Slide and Release are wanted** (they wait on question 1): after the run in 2,
   `python scripts/mark_release.py --timeline out/rcc-lines-run/timeline.json --video ~/.cache/curling_score/videos/Go_JOSxJPsQ.mp4 --rocks <END:ROCK,...> --out out/rccrelease1`
   and mark the first frame the hand is off, as `datasets/releasemarks/README.md` describes; 100 rocks is a
   start. The trainer (`scripts/release/`) is written for a CUDA box and trains from ImageNet weights on
   about a thousand marks; tuning `release1.pt` on a hundred from here has not been tried.
5. **Two things about the club:** when the skip throws, who holds the broom, and is it always a real broom
   (the pad on end 1 rock 13 is dark grey and held end on)? And is there any camera, even one not on the
   stream, that sees the ice between the hog lines?
6. **Whether to ask Will** for "At the hog line" on a line with no final line, and whether late spin from the
   far end is worth building.
