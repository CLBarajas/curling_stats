# Rochester's sheets B, C and D

Sheet A (`Go_JOSxJPsQ`, 2026-11-04) is where every Rochester profile setting and both models came from. This
is the same work for the other three sheets: one finished game each, its calibration, its scoreboard, and how
`rcc1b` (overheads) and `rcc2b` (end cameras) do on it. Measured 2026-11-11 on branch `rcc-sheets`.

| sheet | profile | video | game |
|---|---|---|---|
| A | `rochester` | `Go_JOSxJPsQ` | 2026-11-04 Wed Comp (the control) |
| B | `rochester-b` | `Df66u7Sv84c` | 2026-11-10 Tues Open, Mendick v Hahn |
| B | `rochester-b` | `JA_qWEzaABk` | 2026-11-09 Mon Open, Schubart v Denny: **no game on sheet B** (below) |
| C | `rochester-c` | `R-7qQORH0dQ` | 2026-11-09 Mon Open, Aimi v Curtis |
| D | `rochester-d` | `Vu6sd-fo0PE` | 2026-11-09 Mon Open, Lisbon v Egan |

`JA_qWEzaABk` is listed on @RCCStreamingSheetB as a game, but the sheet is empty for the whole stream (40
frames from 0 to 7606 s) and the board never changes: the cards are a previous game's. It still served to check
the end cameras on an empty plate. Nothing in the pipeline can tell a stream of an empty sheet from a game: the
models find nothing and the board reader reads the stale cards as this game's score (4-1 after five ends).

## Results

Calibration is `analyze.calibrate_from` as `analyze` calls it: 18 raw keyframes, every 90th, across the stream.
End-camera rows are in the end camera's own rectangle (`side_rects`). The board rectangle is
`(322, 850, 1276, 226)` on every sheet: the board camera's place in the composite is the same, the board's
place inside its picture is not (`strip_x` and the rest below).

| | A (control) | B (`Df66u7Sv84c`) | C | D |
|---|---|---|---|---|
| top overhead | 85.8 px/m, 3.15 cm | 87.7 px/m, 3.41 cm | 85.5 px/m, 2.56 cm | 84.2 px/m, 1.46 cm |
| bottom overhead | 84.6 px/m, 1.27 cm | 84.9 px/m, 2.26 cm | 85.3 px/m, 1.33 cm | 85.4 px/m, 1.74 cm |
| left end camera (top house) | tee 390.6, hog 805.5, d 16.02 m, ring 1.4 cm, centre 154 rows | tee 406.1, hog 744.0, d 16.76 m, ring 3.4 cm, centre 128 rows | tee 427.2, hog 786.5, d 16.65 m, ring 1.4 cm, centre 136 rows | tee 418.5, hog 788.7, d 15.59 m, ring 3.4 cm, centre 123 rows |
| right end camera (bottom house) | tee 386.1, hog 802.6, d 15.53 m, ring 2.6 cm, centre 153 rows | tee 421.0, hog 753.6, d 15.81 m, ring 4.1 cm, centre 128 rows | **fails: its hog line is not in the picture** | tee 440.6, hog 811.7, d 15.77 m, ring 4.6 cm, centre 137 rows |
| board `strip_x`, `card_v`, `top_row` | 0.125-0.90, 80, (1.10, 0.04) | 0.125-0.875, 100, A's | 0.125-0.925, 130, (1.10, -0.12) | 0.105-0.875, 80, A's |
| board read vs eye | matches (fixture) | matches, except the last card, an 8, at 0.986 (unread) | matches | matches |
| top row is | red (end 1, close) | red (end 1) | red (end 1) | red (end 1) |
| `rcc1b`, overheads | usable | usable | usable | usable |
| `rcc2b`, end cameras | usable | usable | usable | usable |

`JA_qWEzaABk` (sheet B, empty) gives the same end-camera fits as `Df66u7Sv84c` to within a pixel (tee 407.2 and
421.8, hog 745.6 and 753.9, ring 3.6 and 4.2 cm), so sheet B's cameras did not move between 11/9 and 11/10.

### Calibration

- **Overheads**: all six insets fit with the profile as it was (84-88 px/m, residuals 1.3-3.5 cm, sheet A
  1.3-3.2). Sheet B's top inset reads 87.7 px/m on both of its games against 84-86 elsewhere: its camera hangs
  a little lower, or the inset is scaled; nothing needed changing.
- **Sheet B, left end camera** failed ("centre line traced on only 16 rows"). The camera looks down the dark
  strip between sheets B and A, whose paint (H 114, S 29, V 85-100) is inside the purple band; the morphological
  close joined it to the house's 12-foot ring, and the "house" ran from row 218 to 697. The house's purple is
  V 120 and up (1st percentile), so the B/D end-camera purple now starts at V 100. On D the fit is unchanged by
  it (tee 418.4 either way).
- **Sheet C, left end camera** failed ("no ice below the house to look for a hog line"): the camera sees its own
  house smaller than sheet A's, and the overhead inset in the same rectangle, also teal, was the larger blob. The
  inset is now painted out of the plate before an end camera is fitted (`endcam.hide`). C's teal also reads
  bluer on this camera (H 100-101 against A's 95, so A's band, to H 99, found almost none of it); C's end-camera
  teal runs to H 106. With both, it fits better than A (ring 1.1-1.4 cm).
- **Sheet C, right end camera**: the board camera's picture starts above this camera's hog line, so the line is
  not in the composite at all (checked on frames with a stone at the bottom of the view, `C/bottom.jpg` in the
  session's scratch). Before this branch, `dark_hog_row` took the darkest row anyway, a 14-level shading step
  at row 721, and the fit "succeeded" at d = 107-156 m. It now refuses a row less than 30 grey levels under the
  ice (real lines are 68-85 on A and B): "no dark hog line in view". **No profile setting can fix this**; see
  "For Chris".
- **Sheet D** fit both end cameras with the B/D profile as it was.

### Scoreboard

The reader needed three things to read B, C and D, all now per board in `FixedBoard`, with A's values the
defaults:

- **Where the numerals are** (`strip_x`): B's "18" ends at 0.87 with BLANK ENDS from 0.88, inside A's 0.90;
  C's "18" ends at 0.92, past it; D's "1" starts at 0.115, A's strip starts at 0.125.
- **Numerals run together**: B's softer camera merges the two digits of 10-18 into one glyph (20 glyphs, not
  27), so the slot finder now groups glyphs into numerals (digits of one numeral are 5 px or less apart on A,
  numerals 10 px or more) and checks that all 18 sit on the even spacing (within 0.25 of a slot).
- **What a card looks like** (`card_v`): B's black cards blur to V 75-115, C's bright camera shows them navy
  (V 105-125); A's bar is V 80. Bare slots stay under 0.13 at the new bars, cards over 0.50.
- **Where the top cards hang** (`top_row`): C's top team's cards hang over the strip's top edge, and cut off
  there a "2" read at 0.55. C's band now reaches 0.12 of a strip height into the strip (every card 0.998+). C's
  board also sits so high that the top band starts a row above the picture: up to 0.15 of a strip height may
  run off it.
- The strip's ink range is now 0.20-0.60 (was 0.50): C's bolder numerals are 0.45-0.52 ink. A, B and D read the
  same strip rows as before.

What each board read at the end of its stream (`read_game_board` with `fixedboard.reader`), checked against a
median of the board crop by eye:

- **B** (`Df66u7Sv84c`): top 3, 4, 5, 6 on slots 1, 2, 4, 5; bottom 1, 2, 7, 8 on slots 1, 2, 5, 6. All read
  except the 8 (0.986, under `MIN_CONFIDENCE` 0.99), so `read_game_board` used its 6884 s read: ends 1-7, end 8
  unread. A softer bar for B alone would take it; I left the bar where it is.
- **C**: top 1, 2, 4, 5 on slots 1, 2, 3, 5; bottom 3 on slot 2. Five ends posted by the end of the stream.
  At 39 minutes the 1 and 2 cards were on the bottom row; someone moved them to the top later. A read in that
  window credits ends 1-2 to the wrong team, and nothing can tell.
- **D**: top 2, 4, 6 on slots 1, 2, 5; bottom 1, 3, 5 on slots 3, 4, 6. Six ends posted.

**Which row is which team**: for end 1 of each game I found the frame before the house was cleared and judged
the count by eye from the overhead. C (red on the button, blue second: red 1), D (three blues: blue 3) and B
(blue lies one after the last red) all agree with top = red, bottom = blue. A agrees too, but end 1 was close
(the last red about 77 px from the button against a blue at about 80, in a scaled frame). One end a sheet: the
convention holds on these four games, not proven for the club.

### Stone models

Twenty frames evenly spread over each game (6%-94% of the stream), both overhead insets (`rcc1b`, imgsz 448)
and both end-camera crops from 80 rows above the tee to the bottom of the view (`rcc2b`, imgsz 800), conf 0.30
as `analyze` and `farfollow` use. I looked at every crop: 40 overhead and 40 end-camera crops a sheet.

| | overhead boxes | overhead errors seen | end-camera boxes | end-camera errors seen |
|---|---|---|---|---|
| A (control) | 79 | a small box in an inset's top-left corner on empty houses (6278, 7368 s) | 103 | not counted |
| B (`Df66u7Sv84c`) | 42 | 2 stones cut by a panel's right edge missed (1924, 2289 s); no wrong colours, no false boxes | 76 | 2 false: a blue vest (4104 s), a red shoe (7374 s); no wrong colours |
| C | 54 | at most 1 stone half out of the panel missed (6292 s); no wrong colours, no false boxes | 114 | 2 false: a blue jacket (837 s), a red broom head among stones (6657 s); no wrong colours |
| D | 84 | 1 doubtful 0.35 box at a panel edge (3748 s); no misses seen, no wrong colours | 134 | about 3 false: a red shirt and a shoe in a crowd at the house (2653, 3018 s); no wrong colours |

- **Both models carry over to all three sheets as they are.** Every stone I could see on the ice was boxed,
  in its own colour, on every sheet and camera; the misses are stones half out of an overhead panel. No
  review set was built and nothing needs retraining.
- The end-camera false boxes are red or blue clothing and shoes, in crowded frames around the house. I did not
  count A's end-camera boxes the same way, so I can't say whether this is more than on A.
- The end cameras also box real stones on the neighbouring sheets at the left and right edges of the view
  (C at 472, 837, 5202, 7387 s and others; A's left camera shows the next sheet's house too). Whether these
  reach a timeline depends on how the side detections are placed on the sheet, which I did not check.
- The racks of spare stones beside sheet D's right camera are not boxed.

## Full runs (Chris's GPU, 2026-11-11)

`curling-score analyze --club rochester-d|rochester-b --device mps` from this branch, compared with sheet A's
`out/rcc-1104-gpu`. Neither run had the release model: it looks for CUDA only and ignores `--device mps`, so
release times come from the fallbacks on all three sheets.

| | A (`rcc-1104-gpu`) | D (`rcc-d-1109`) | B (`rcc-b-1110`) |
|---|---|---|---|
| ends, throws | 8, 115 | 7, 112 | 8, 128 |
| entry into the house | 108 | 105 | 112 |
| far hog line | 76 | 77 | 91 |
| splits | 58 | 60 | 73 |
| release times | 107 | 103 | 107 |
| target broom | 95 | 91 | **43** |
| stone count vs board, ends posted | 5 of 7 agree | 5 of 6 agree (end 6: 4 against 3) | 6 of 7 agree (end 5: 0 against 2) |

- **D** is as good as A. The game stopped after 7 ends (last throw 7333 s of 7858).
- **B, end 5**: the board's red 2 is right (two reds in the house at 4094 s, no blue). The run read the house at
  4108 s or later, after the clear had started, and counted nothing. A timing question for end assembly.
- **B, hammer in end 5**: the run has red with the hammer (yellow threw first; a blue was first into the house
  at 3378 s), but the rules say yellow, because red stole end 4. Red did score end 4 by both the board and the
  stones, and end 4's first stone was red (a guard, on the end camera at 2500 s). So the teams most likely threw
  end 5 out of order, and the run reports what happened; `hammer_expected` flags it.
- **B, target broom on 43 throws** against 91-95 on A and D. Not looked into; it belongs to the line and broom
  work.
- B's end 1 runs from 27 to 606 s, under ten minutes. The top house has play from 30 s to its clear at 615 s
  (overhead counts), so it is a real end, not a warm-up.

## Changes on `rcc-sheets`

- `clubs.py`: `rochester-b`, `rochester-c`, `rochester-d`; `rochester-bd` keeps B and D's common paint and
  cameras, with its left end camera's purple from V 100, and still has no board. `rochester` (A) is unchanged.
- `game/fixedboard.py`: per-board `card_v` and `top_row`; slots found from numerals, not glyphs, with an
  even-spacing check; strip ink to 0.60; a card row may run 0.15 of a strip height off the picture.
- `geometry/endcam.py`: `hide()` paints the overhead insets out of the plate; `dark_hog_row` refuses a "line"
  less than 30 grey levels under the ice.
- `analyze.py`: two lines in `_end_views`, so end cameras are fitted on the plate with the insets hidden.
- Tests: board fixtures for B, C and D (`tests/fixtures/fixedboard/rochester_{b,c,d}_*.png`) and their reads;
  the hog-line refusal and `hide`.

Run: `tests/test_weights.py`, `tests/test_calibrate.py`, `tests/test_endcam.py` and `tests/test_fixedboard.py`
pass. The whole suite has failures in `test_conceded.py`, `test_fpframes_side.py` and `test_live_session.py`
that are on `rcc`'s tip (`47db7c7`) without these changes too, and errors from `fastapi` not being installed in
the venv.

## Verified and inferred

Verified by running code or looking at frames: every number in the tables; the empty sheet B stream; C's right
camera not showing its hog line; each board read against its median crop; end 1 of each game; every model crop
named above.

Inferred, not checked: that the new profiles hold on other games on the same sheets (only B was seen on two
games; its end cameras agree to a pixel); that top = red is the club's convention rather than what these four
games' players did; that the end-camera false boxes would survive into a timeline; how a full analysis does on
B, C or D (none was run).

## For Chris

1. **Sheet C's right end camera can't see its hog line.** The composite gives the board camera the rows where
   that line would be. Either the camera is aimed lower at the club, or C's composite gives that camera more
   rows. Until then, `analyze` drops both end cameras on C, because `_end_views` gives up on all splits when
   one camera fails. Keeping the left camera alone would need a change there, and another session owns that
   file.
2. **Stale boards**: `JA_qWEzaABk` shows that a stream of an empty sheet reads as a game with a score. Is there
   a schedule or a title marker that says which sheets were in use? If not, "no stone seen all stream" could
   flag it.
3. **B's 8 at 0.986**: lower `MIN_CONFIDENCE` for B's board, or accept a last end unread on B when an 8 is up?
4. The next step is a full analysis on another sheet, on your GPU (about 25 minutes each; run one at a time).
   D has everything (both end cameras, the board):

   ```bash
   cd ~/Developer/GitHub/wdimmit/curling_stats-sheets && PYTHONPATH=src ../curling_stats/.venv/bin/python -m curling_score.cli analyze "https://www.youtube.com/watch?v=Vu6sd-fo0PE" --club rochester-d --device mps --out ../curling_stats/out/rcc-d-1109
   ```

   And B:

   ```bash
   cd ~/Developer/GitHub/wdimmit/curling_stats-sheets && PYTHONPATH=src ../curling_stats/.venv/bin/python -m curling_score.cli analyze "https://www.youtube.com/watch?v=Df66u7Sv84c" --club rochester-b --device mps --out ../curling_stats/out/rcc-b-1110
   ```

   This branch's `analyze.py` differs from `rcc`'s only by the two lines above. The end-assembly work in progress
   on `rcc` is not in it.
