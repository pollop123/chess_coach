# Evaluator calibration

`evaluation_corpus_v1.json` is a reproducible Stockfish self-play corpus built by
`build_evaluation_corpus.py`. It contains 500 unique, legal, non-terminal
positions from 40 generated games. Every game belongs to exactly one split, so
adjacent positions from a game cannot leak across train, validation, and test.

Current distribution:

| Split | Games | Positions | Opening | Positional | Tactics | Endgame |
|---|---:|---:|---:|---:|---:|---:|
| train | 28 | 350 | 56 | 214 | 43 | 37 |
| validation | 6 | 75 | 12 | 30 | 8 | 25 |
| test | 6 | 75 | 12 | 42 | 9 | 12 |

Rebuild it with:

```bash
.venv/bin/python backend/build_evaluation_corpus.py \
  --stockfish /opt/homebrew/bin/stockfish \
  --games 40 --target 500 --nodes 3000 --max-plies 96 --sample-every 4
```

Run a game-grouped validation benchmark with:

```bash
.venv/bin/python backend/teaching_accuracy_benchmark.py \
  --profile release \
  --stockfish /opt/homebrew/bin/stockfish \
  --corpus backend/calibration/evaluation_corpus_v1.json \
  --split validation \
  --output backend/calibration/validation-report.json
```

## 2026-07-16 activity-weight decision

The original 23-position release set suggested enabling `piece_activity=25`:
overall top-3 increased from 65.2% to 69.6%, recall from 78.3% to 82.6%, and
positional top-3 from 20% to 40%, with tactics and endgame unchanged.

The larger validation split did not confirm a positional improvement:

| Weight | Overall top-3 | Recall | Opening top-3 | Positional top-3 | Tactics top-3 | Endgame top-3 | Runtime |
|---|---:|---:|---:|---:|---:|---:|---:|
| activity 0 | 72.0% | 57.3% | 66.7% | 70.0% | 87.5% | 72.0% | 313.3s |
| activity 25 | 72.0% | 58.7% | 58.3% | 70.0% | 87.5% | 76.0% | 356.1s |

A second activity phase curve based on minor-piece development was also tested
on all 42 validation opening/positional positions. It left positional top-3 at
70.0% and opening top-3 at 58.3%. Therefore the production activity weight
remains zero. The phase-aware calibration path stays available, but the feature
semantics must improve before it is enabled again.

The test split remains untouched for a final candidate; do not tune against it.

## 2026-07-16 final search candidate

Three semantics-preserving hot-path changes were retained:

- quiescence orders only captures and promotions, instead of scoring every
  legal move and discarding quiet moves afterward;
- material/PST and king-exposure evaluation use bitboards instead of temporary
  piece-map dictionaries;
- quiescence uses python-chess's legal-capture generator and adds quiet
  promotions explicitly.

On `generated_016_012`, fixed depth 4 kept the same `Qe2`, score, and 78,350
nodes while wall time fell from 12.40s to about 4.46s. At the unchanged 1.5s
production budget, validation depth-5 completions increased from 3/75 before
the search work to 27/75 in the final candidate.

Stockfish 18 results at 12,000 judge nodes per analysis:

| Split | Positions | ACPL | WDL expectation loss | Near-best | Blunders | Major hangs | Missed mates |
|---|---:|---:|---:|---:|---:|---:|---:|
| Validation, pre-optimization | 75 | 43.2 | 6.04% | 64.0% | 10.7% | 0 | 0 |
| Validation, final | 75 | 35.7 | 4.81% | 66.7% | 9.3% | 0 | 0 |
| Untouched test, final | 75 | 27.8 | 4.60% | 64.0% | 9.3% | 1 heuristic flag | 0 |

The test "major hang" flag is a heuristic false positive: Stockfish assigned
zero centipawn and zero expectation loss to the move. The result is still not
strong enough to market as a high-level engine: test positional near-best is
61.9%, and seven test positions cross the 20% WDL-loss blunder threshold. The
UI therefore remains honestly labelled `中階加強`. A 5s diagnostic fixed only
two of those seven blunders, so merely raising latency was rejected; the next
iteration needs better strategic evaluation and selective-search semantics.

Pawn-structure weight 100 was also rejected on a grouped train screen (32
positions): positional WDL loss rose to 13.83%. A conservative null-move trial
produced an identical time-limited A/B result and was removed. These rejected
experiments are recorded here so they are not accidentally reintroduced.

## 2026-07-16 only-legal-move extension decision

A Deep Blue-inspired, strictly bounded extension was tested: when a node had
exactly one legal move, its child retained the current depth, with no more than
two such extensions per search path. The transposition table was partitioned
by extension mode and remaining credit during the experiment.

At fixed depth 3 on 24 grouped validation positions, the extension triggered
only three times, increased nodes by 1.0% (121,770 to 122,989), and changed no
move. A 32-position, 1.5-second Stockfish A/B was also exactly neutral on every
accuracy metric: ACPL 29.2, WDL expectation loss 5.37%, near-best 62.5%, and
blunders 12.5%. It changed no move, while two positions completed one fewer
nominal ply (4 to 3 and 5 to 4).

The experiment failed the predeclared benefit/cost gate and was removed from
production code. The likely reason is that the existing quiescence search
already searches every legal check evasion, leaving too few useful only-move
nodes for this broad rule to improve decisions. The raw reports are
`forced-extension-screen-baseline.json` and
`forced-extension-screen-candidate.json`.

## 2026-07-16 quiet contextual pawn-shelter decision

A first fast/slow evaluation slice was implemented as an experimental,
default-zero feature. `quiet_pawn_shelter` is evaluated only at non-check
quiescence nodes. It penalizes missing shelter pawns only after the king has
committed to a wing, scales danger by the opponent's remaining queens and
rooks, and tapers to zero in the endgame. Ordinary public evaluation remains
unchanged.

At fixed depth 3 on 24 grouped validation positions, weight 100 changed one
move, reduced total nodes by 3.6%, and had essentially unchanged wall time. On
the 32-position, 1.5-second Stockfish screen, however, weight 100 worsened ACPL
from 29.2 to 29.8 while WDL loss, near-best rate, and blunder rate were
unchanged. The only changed move worsened from 86 cp to 104 cp loss and its
completed depth fell from 3 to 2. Weight 50 was accuracy-neutral and
move-neutral, but one position completed depth 3 instead of 4.

The production weight therefore remains zero. The feature and the new
repeatable `stockfish_calibration.py --feature-weight NAME=PERCENT` interface
remain available for later joint rather than isolated calibration. Reports:
`contextual-shelter-screen-baseline.json`,
`contextual-shelter-screen-candidate.json`, and
`contextual-shelter-screen-weight50.json`.

## 2026-07-19 transposition-table value decision

The existing transposition table was measured before attempting a redesign.
A `use_tt` search switch and `stockfish_calibration.py --no-tt` were added so
the table can be bypassed completely while repetition detection and every other
search feature remain enabled.

Two alternating fixed-depth-3 passes over 24 grouped validation positions
produced identical moves and scores in all 48 comparisons. TT-on reduced nodes
from 275,816 to 243,540 (11.7%) and wall time from 14.23 s to 13.23 s (7.1%).
There were 13,606 hits and 6,538 useful cutoffs.

On the 32-position, 1.5-second Stockfish screen, TT-on reduced total searched
nodes from 448,821 to 370,976 while completing more iterations: depth-5
positions increased from 8 to 11, and the two depth-2 completions disappeared.
WDL expectation loss improved from 5.68% to 5.37%; blunders remained 12.5%.
ACPL moved in the opposite direction, from 28.2 to 29.2, because selective
search and different completed iterations changed five moves. The WDL result,
depth distribution, and deterministic fixed-depth speedup support retaining
the table, but not investing in a larger or more complex replacement scheme.

The next TT work, if any, should be limited to semantics-preserving hot-path
cleanup such as reusing the Zobrist hash already calculated for repetition.
Raw reports: `tt-screen-disabled.json` and `tt-screen-enabled.json`.
