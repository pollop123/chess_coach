# Search and evaluation research notes

This note translates primary chess-AI research into changes appropriate for
this project: a self-contained Python alpha-beta engine with a roughly 1.5 s
interactive move budget. It is a design record, not evidence that a proposed
change has passed the project's grouped validation benchmark.

## Executive conclusion

The literature does not support simply adding more static bonuses or raising
the global depth. The most relevant pattern is:

1. retain a minimum full-width search depth as tactical insurance;
2. spend extra search only on demonstrably forcing or singular lines;
3. evaluate quiet leaves with contextual, phase-aware knowledge;
4. keep expensive knowledge off the hottest path or update/cache it cheaply;
5. tune feature combinations by move ordering or concordance, then validate by
   games and untouched positions;
6. treat engine strength and human-like teaching difficulty as separate layers.

This also explains the project's recent results. Fixed castling, raw pawn
structure, activity, and graded king-safety changes can look locally plausible
but fail grouped validation because their context is underspecified or their
cost reduces completed search depth.

## What the original research says

### Shannon: search volatile chess; evaluate stable chess

Claude Shannon's 1950 paper distinguishes exhaustive search from selective
search and argues that approximate evaluation should be applied to relatively
quiet positions. Checks, captures, attacks on major pieces, mate threats, pins,
and other violent changes belong primarily in the searched continuation rather
than being hidden inside a static score. His example evaluation knowledge also
includes weak and passed pawns, open files, seventh-rank rooks, outposts,
mobility, king-zone attacks, and king-pawn weakness. He explicitly proposes
determining weights experimentally.

Project implication: improve bounded quiescence/forcing continuations before
adding static tactical bonuses. Strategic features should be judged at quiet
leaves and should not compensate for an unresolved capture or check sequence.

Primary source: [Shannon, *Programming a Computer for Playing Chess* (1950)](https://walkofmind.com/programming/chess/Shannon%20-%20Programming%20a%20computer%20for%20playing%20chess.pdf)

### Deep Blue: no single trick, and not merely more depth

The final Deep Blue system combined massive parallel search with a minimum
full-width depth, strongly non-uniform extensions, a complex evaluation
function, opening knowledge, endgame databases, and automated tuning. The
authors explicitly say that no single element explains the result.

The evaluation was split into fast and slow knowledge. Cheap, high-value terms
could be computed everywhere, while richer control, king-safety, pawn,
blockade, outpost, development, trapped-piece, and rook patterns were handled
as more complex knowledge. Many scores changed with material and context. For
example, rook value was not just a fixed open-file bonus: blockage, protection,
safe access to the seventh rank, and other relationships mattered.

The team's tuning process is particularly relevant here. Automated experiments
identified noisy features that did not converge without added context;
mobility, king safety, and rook-on-file knowledge were substantially revised.
Comparison training also showed that their hand-set pawn-shelter weights were
too small before the 1997 match.

Project implication: use a cheap leaf score plus selectively invoked or cached
contextual evaluation. Do not enable raw mobility, rook-file, king-safety, or
pawn bonuses solely because the chess concept is sound. Their representation,
phase scaling, interactions, and runtime cost must pass A/B validation.

Primary sources:

- [Campbell, Hoane, and Hsu, *Deep Blue* (IBM Research, 2002)](https://research.ibm.com/publications/deep-blue)
- [Official journal record and DOI](https://www.sciencedirect.com/science/article/pii/S0004370201001291)

### Singular extensions: deepen only when the position supplies evidence

The ChipTest/Deep Thought singular-extension work extends a move when the
current search shows it is substantially better than every alternative. It
uses dynamic evidence from the search rather than a large catalogue of chess
rules and was reported as a major factor in ChipTest's performance. Deep Blue
later combined several extension credits, delayed some extensions until enough
forcing evidence accumulated, and capped their growth.

Project implication: the first search experiment should be conservative and
bounded. Candidates are an extension for an only legal reply, a near-root
singular extension supported by a sufficiently deep transposition-table entry,
and a near-promotion passed-pawn extension. Each path needs a strict extension
budget. A minimum unextended depth remains the tactical safety net.

Primary source: [Anantharaman, Campbell, and Hsu, *Singular Extensions: Adding Selectivity to Brute-Force Searching* (1988)](https://journals.sagepub.com/doi/10.3233/ICG-1988-11402)

### Null-move pruning is not an automatic priority

Null-move search has strong historical results as a selective heuristic, but
the Deep Blue authors did not deploy it in the final system because they did
not consider its tactical insurance sufficiently established for their design.
This project's conservative null-move experiment was neutral and was removed.

Project implication: do not prioritize another null-move implementation until
the more directly supported forcing-line extensions have been tested.

Primary source: [Donninger, *Null Move and Deep Search* (1993)](https://journals.sagepub.com/doi/10.3233/ICG-1993-16304)

### Tune rankings, not just centipawn distances

Comparison training and later concordance work treat an evaluation function as
an ordinal predictor: it must rank alternatives correctly. Tesauro reported
that plain one-ply comparison training was ineffective, while adding
quiescence produced high-quality weights that continued to help at deeper
search. Gomboc, Buro, and Marsland formalized tuning by maximizing rank
concordance rather than assuming centipawn labels form a perfect interval
scale.

Project implication: retain the game-grouped train/validation/test split, but
construct pairwise candidate-move examples. Score candidates after quiescence
or a shallow fixed search, optimize ranking/concordance jointly across feature
weights, and reserve ACPL/WDL/blunder metrics for final engine-level selection.
Independent one-feature screens remain useful rejection tests, not the final
tuner.

Primary sources:

- [Tesauro, *Comparison Training of Chess Evaluation Functions*](https://www.researchgate.net/publication/262334416_Comparison_training_of_chess_evaluation_functions)
- [Gomboc, Buro, and Marsland, *Tuning Evaluation Functions by Maximizing Concordance*](https://www.sciencedirect.com/science/article/pii/S0304397505005967)

### Learned evaluators: useful direction, wrong immediate scale

KnightCap demonstrated that TDLeaf could substantially improve a chess
evaluation through actual games. Giraffe later showed that learned evaluation
and search representations can rival strong hand-crafted components. Modern
Stockfish uses NNUE: sparse inputs that change little after each move, shallow
integer layers, and incrementally updated accumulators make learned evaluation
compatible with alpha-beta CPU search.

Project implication: a small learned evaluator is a credible future phase, but
copying modern NNUE into the current Python engine is not the next low-risk
step. Its advantage depends on a large training set, quantized inference,
incremental state, and extensive match testing. First adopt the transferable
ideas: sparse/contextual features, cheap updates, and ranking-oriented data.

Primary sources:

- [Baxter, Tridgell, and Weaver, *Learning to Play Chess Using Temporal Differences*](https://arxiv.org/abs/cs/9901001)
- [Lai, *Giraffe: Using Deep Reinforcement Learning to Play Chess*](https://arxiv.org/abs/1509.01549)
- [Official Stockfish NNUE technical documentation](https://official-stockfish.github.io/docs/nnue-pytorch-wiki/docs/nnue.html)

### Teaching difficulty is not the same as engine weakness

Maia was trained to predict human moves at specified rating levels. Its result
shows why a teaching opponent should not be created only by lowering depth or
randomly choosing an inferior engine move: a superhuman engine and a human at
the same nominal win rate make different kinds of decisions and mistakes.

Project implication: keep a strongest-available core search. Later add a
separate teaching policy that chooses among evaluated candidates according to
rating-calibrated human error patterns. This can preserve tactical safety while
making an amateur opponent recognizable and pedagogically useful.

Primary source: [McIlroy-Young et al., *Aligning Superhuman AI with Human Behavior: Chess as a Model System* (KDD 2020)](https://www.cs.toronto.edu/~ashton/pubs/maia-kdd2020.pdf)

## Recommended experimental sequence

### Experiment 1: bounded forcing extensions

- Keep the current minimum full-width iterative-deepening depth.
- Add only-legal-reply/check-evasion extension first.
- Add a strict per-line extension-credit cap.
- Measure node growth, completed depth, tactical regressions, ACPL, WDL loss,
  near-best rate, and blunders on grouped validation.
- Only then trial TT-backed singular and advanced-passed-pawn extensions.

Acceptance gate: tactics cannot regress; validation WDL loss and blunders must
improve without unacceptable latency-tail growth.

### Experiment 2: two-tier contextual evaluation

- Define a fast score used at every leaf: material, tapered PST, and only the
  cheapest proven terms.
- Define a slow/contextual score for stable quiet leaves or important PV/root
  nodes, with caching where possible.
- Start with pawn shelter scaled by opposing heavy material, then contextual
  passed pawns and rook activity. Avoid fixed castling bonuses and raw global
  mobility.

Acceptance gate: compare both chess accuracy and completed search depth. A
feature that improves static labels but loses more through search slowdown is
rejected.

### Experiment 3: pairwise joint tuning

- Generate candidate moves for the 350-position training split.
- Cache Stockfish ranking/WDL labels once.
- Evaluate candidates after quiescence or a shallow fixed search.
- Optimize a small, regularized feature vector for pairwise concordance.
- Select on validation; touch the test split once for the final candidate.

### Experiment 4: exact small endgames

- Add KPK bitbase first, followed by compact, verifiable rules or tablebase
  probes for supported low-material endings.
- Keep exact results separate from heuristic evaluation.

### Experiment 5: rating-calibrated teaching policy

- Collect human games by rating band only after the strong core stabilizes.
- Learn or estimate which near-best and mistake classes players at each level
  actually choose.
- Use that distribution to choose among core-engine candidates; never inject a
  random catastrophic blunder merely to reduce Elo.

## Current decision

Do not enable the currently disabled pawn-structure, piece-activity,
rook-activity, or graded king-safety weights yet. The smallest bounded
only-legal-move extension was implemented and rejected: a 32-position grouped
A/B changed no move or accuracy metric and reduced completed depth in two
positions. The existing quiescence treatment of check evasions appears to make
this trigger too sparse. The next experiment should therefore be the two-tier
contextual evaluation design. Its first isolated feature, quiet contextual pawn
shelter, was also screened and left at weight zero: weight 100 slightly worsened
ACPL, while weight 50 was neutral and reduced completed depth in one position.
These results reinforce the comparison-training evidence that contextual terms
should next be calibrated jointly against candidate-move rankings rather than
enabled one at a time from hand-selected weights.
