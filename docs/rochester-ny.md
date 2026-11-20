# Rochester Curling Club (Rochester, New York)

This branch, `rochester-ny`, adapts curling_stats to Rochester Curling Club's sheet streams. It's the club in Rochester, New York, not the Curling Club of Rochester in Minnesota. It's built on Will Dimmit's `dfw` branch, and anything in it is his to take.

*Last updated 2026-11-19.* Every change from `dfw`: [compare `dfw...rochester-ny`](https://github.com/CLBarajas/curling_stats/compare/dfw...rochester-ny).

## The streams

- **One YouTube channel per sheet**, `@RCCStreamingSheetA` to `D`, and one stream per game. 1920 × 1080.
- **Each stream is a composite.** Two end cameras fill the top half, side by side. Each sits behind its own hog line, looking at its own house. Two small overhead insets sit in the bottom corners, and a camera on the wall scoreboard fills the bottom centre.
- **The overheads show the house only**, about two metres either side of the tee. Stones enter them from the bottom.
- **The house paint alternates.** On sheets A and C the left house is teal with a purple 4-foot, and the right house is the reverse. On B and D it's the other way round.
- **Red and blue stones.** Blue is the models' `yellow_stone` class. The viewer says and draws blue.

## What makes Rochester hard

Will built the pipeline at Granite, where the overheads see from the house out past the hog line. Here they don't. A guard stops where no overhead can see it. A delivery enters an overhead only in its last two metres. A stone knocked or cleared looks, from above, a lot like a throw.

So the end cameras carry more of the load here than anywhere else in the project.

## How Rochester is read

- **Profiles:** `rochester` (sheet A) and `rochester-b`, `rochester-c`, `rochester-d` in `src/curling_score/clubs.py`. `--club rochester` picks the sheet's profile from the stream's channel.
- **Models:** `rcc1b.pt` for the overheads (tuned from Will's `overhead-3`) and `rcc2b.pt` for the end cameras (tuned from `cin3a`). How they were made, and their checksums: [`datasets/rcc1/README.md`](../datasets/rcc1/README.md), [`datasets/rcc2/README.md`](../datasets/rcc2/README.md).
- **The end-by-end count** (Rochester only: `throws_from_end_camera`). The camera behind the thrower counts the end's deliveries. When it sees a full end in turn, those are the end's rocks. A stone the overhead saw move with no delivery behind it is then knocked or cleared, not thrown.
- **Guards** are placed by the end camera facing the house, read 10 s after the stone crosses the far hog line. Their positions are estimates, good to tens of centimetres.
- **The wall scoreboard** has a camera of its own at a fixed spot (`game/fixedboard.py`). People walking past are removed with a median over eight minutes, and Will's digit classifier reads the cards.
- **Lines:** each end camera gives a delivery's line over its last three metres to the hog line. There's no "final" line, by design.
- **Sheet C's right end camera** can't see its hog line. It's placed from the rings instead, taking the camera to be 16 m from its tee. On the seven cameras that do show their hog line, that puts a guard four metres out within 4 cm of where the painted line does.

## Results so far

| Sheet | Game | Rocks found | Notes |
|---|---|---|---|
| A | `Go_JOSxJPsQ`, 2026-11-04 | 123 of 128 | The stream stops five rocks early |
| C | `vztdzCNM2fk`, 2026-11-11 | 128 of 128 | Also charted live, during the game |
| D | `Vu6sd-fo0PE`, 2026-11-09 | 112 of 112 | A seven-end game |
| B | `6IUB9KbPkpc`, 2026-10-28 | 127 of 128 | An older stream layout. The 128th rock was never thrown: the game was conceded |
| A | `WSJVZqj2Cpw`, 2026-10-21 | 96 of 96 | A six-end game, in a stream it shares with an earlier match |
| B | `QU4XN1R19TA`, 2026-11-18 | 96 of 96 | A six-end game. Charted live as well, less completely: 93 |

- **Checked by eye:** every doubtful rock in the 10/28 and 11/9 games, and some in the 11/4 and 11/11 games. The other two the least.
- **Every hammer agrees with the scoreboard** on all six games.
- **No harm at Granite**, as this branch stood on 2026-11-17; not run again since. Will's answer-key game (`VXU9xwmugRg`, in `validation/ground_truth.json`) scored the same on this branch as on `dfw`: all 18 deliveries he checked by eye, none of his 8 non-deliveries, and the board. His `scripts/compare_timelines.py` paired all 208 rocks between the two. Most of the Rochester-specific work never runs there, so this shows no harm, not a gain.
- **Tests:** the suite fails exactly the tests that fail on `dfw`, and no others. Most of those need the hosted service's packages, which aren't installed here, or are test stand-ins Will has since fixed on `main`.

## Running it

Install as in the main README (`pip install -e ".[dev,gpu]"`). Then, for a recorded game:

```bash
curling-score -v analyze "https://www.youtube.com/watch?v=Go_JOSxJPsQ" --club rochester --device mps --out out/rcc-a
curling-score serve --out out/rcc-a
```

And live, for a stream that's scheduled or under way:

```bash
curling-score -v live "https://www.youtube.com/watch?v=<id>" --club rochester --device mps --out out/rcc-live
```

- **`-v` goes before the command**, or there's no progress output.
- **`--device mps`** uses an Apple-silicon GPU for every model: about 35 minutes for a two-hour game.
- **The release model looks only for CUDA**, so on a Mac release times come from fallbacks. `CURLING_SCORE_RELEASE_CPU=1` reads them on the CPU instead, slower.
- **Team names aren't read from the stream.** Write them into `games[0].teams` in `timeline.json` after a run.
- **Live, the last end settles only when the stream ends.** For a while after the second-last end the viewer looks stalled.

## Known limits

- **Both models learned from one game** (sheet A, 2026-11-04). They work on all four sheets, but that's four games of evidence.
- **The scoreboard:** the top row is taken to be red (checked on each sheet). Cards for end 10 and later aren't read. The last end's card usually goes up after the stream stops, and players sometimes re-hang cards mid-game.
- **Guards:** a guard is read again at each rock. If someone stands in front of it, it drops off the diagram until it's seen again.
- **Spin isn't read** at Rochester.
- **Repeatability on the GPU** hasn't been checked with fresh detections yet.

## Plans

1. **Games the code hasn't seen.** Two or three new games, one per sheet, run once with no changes and checked by eye. That's the honest accuracy figure.
2. **Finish checking the six games by eye**, sheet A first.
3. **A public viewer** for club members, read-only. Live: [FifthSense](https://fifthsense.barajas.io/), six games, on this fork's GitHub Pages.
4. **Offer the general fixes back to Will**, as small pull requests on whichever branch he prefers.
5. **Things to look into:** on sheet A, end 1's rock 15 has no resting place. On sheet D, end 3's rock 8 has no position. On sheet C, end 1's rock 13 is found but charted hogged. In the 11/18 game on sheet B, the stones counted in the house disagree with the scoreboard in three ends, though every throw is found.
6. **Live:** settle the last end once its stones are cleared, not when the stream ends.
7. **More labelled frames** from other sheets and games, so the models don't rest on one game.
8. **Camera framing** would help more than any code. A few suggestions are with the club: sheet C's right camera, and overheads that show the guard zone.

## Reports

- [`datasets/rcc-lines.md`](../datasets/rcc-lines.md): lines, brooms and spin from the end cameras.
- [`datasets/rcc-sheets.md`](../datasets/rcc-sheets.md): sheets B, C and D, their calibration, scoreboards and models.
- [`datasets/rccbroom/README.md`](../datasets/rccbroom/README.md): the broom set.

## Thanks

To Will Dimmit, who wrote curling_stats and made it public.
