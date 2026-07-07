# Teaching Analysis Engine Design

Date: 2026-07-07
Project: Chess AI Coach

## Goal

Strengthen the project as a mixed play-and-coaching system:

- Keep `/make_move` fast and stable for live play.
- Make `/get_analysis` return deeper, structured teaching evidence that the UI and RAG coach can use.
- Improve teaching value without turning the custom engine into a Stockfish clone or adding speculative heuristics without measurement.

## Current Context

The engine already has:

- Minimax with alpha-beta, PVS, quiescence search, iterative deepening, and recursive timeout enforcement.
- Bounded transposition table with exact/lower/upper flags.
- Polyglot opening-book support.
- Difficulty loss bands and a trickster style overlay.
- Stockfish calibration tooling for ACPL/WPL style checks.
- RAG prompt grounding with verified opening names, legal moves, PV line, and move facts.

The missing layer is structured teaching evidence. Today `/get_analysis` mostly exposes best move, score, PV, and search stats. That is enough to recommend a move, but not enough to explain alternatives, common mistakes, or whether a position is critical.

## Recommended Approach

Add a teaching analysis layer used by `/get_analysis` only. Do not change `/make_move` behavior.

The new engine entrypoint should be:

```python
get_teaching_analysis(
    board,
    base_analysis,
    candidate_count=5,
    depth=None,
    time_limit=None,
)
```

It should use the existing engine primitives rather than introducing a separate search engine.

## API Contract

`/get_analysis` should keep its existing `evaluation`, `game_state`, and `coach_advice` fields. It should add:

```json
{
  "teaching_analysis": {
    "candidates": [
      {
        "move": "g1f3",
        "san": "Nf3",
        "rank": 1,
        "score_cp": 35,
        "display": "+0.35",
        "loss_cp": 0,
        "pv": ["g1f3", "b8c6"],
        "warnings": [],
        "themes": ["opening_principle", "development", "center_control"],
        "reason": "develops_piece"
      }
    ],
    "criticality": "normal",
    "position_themes": ["opening_principle", "development"],
    "best_move_reason": "develops_piece",
    "mistake_warnings": []
  }
}
```

Allowed `criticality` values:

- `normal`: multiple reasonable moves exist.
- `sharp`: candidate scores spread widely or tactical warnings exist.
- `only_move`: the best move is much better than the second candidate.

## Candidate Selection

Candidate moves should be built from:

1. `base_analysis["best_move"]`, always included first if legal.
2. The top moves from `order_moves(board)`.
3. Dedupe while preserving order.
4. Limit to `candidate_count`, default 5.

This keeps the candidate set aligned with moves a player is likely to ask about: checks, captures, promotions, central moves, and the engine best move.

## Candidate Evaluation

For each candidate:

1. Push the candidate on a copy of the board.
2. Search the reply position with the existing `minimax`.
3. Use a conservative candidate depth, normally `max(1, base_analysis["depth"] - 1)`.
4. Convert the score to the original side-to-move perspective.
5. Sort candidates by perspective score.
6. Compute `loss_cp` as the gap from the best candidate.
7. Reconstruct a short PV when available.

The function must not mutate the input board. It must respect a teaching-analysis time budget and return partial candidates rather than failing the whole analysis on timeout.

## Warning Rules

Candidate warnings should be rule-based and conservative:

- `hangs_major_piece`: existing `major_piece_loss_after_move` returns true.
- `large_eval_drop`: `loss_cp >= 150`.
- `misses_mate`: the best candidate appears to force mate but this candidate does not.
- `allows_mate_threat`: after the move, opponent has an immediate checking mate or a mate-like evaluation swing.

Warnings are evidence for the coach. They should not be phrased as long natural-language advice inside the engine layer.

## Teaching Themes

Themes are short labels generated from board and move facts:

- `opening_principle`: position is within the opening range.
- `development`: a knight or bishop leaves its starting square.
- `center_control`: a central pawn move or move into/through central squares.
- `tactics`: check, mate, capture, promotion, or a forcing PV.
- `king_safety`: move gives check, attacks king-zone squares, or reduces opponent replies.
- `endgame`: six or fewer pieces, promotion, or king-and-pawn/queen conversion.
- `only_move`: best candidate exceeds second candidate by at least 150cp.

These labels should be stable and testable. The RAG layer can turn them into friendly Chinese explanations.

## Best Move Reason

`best_move_reason` should be a compact reason code, selected from the strongest available evidence:

- `checkmate`
- `wins_material`
- `avoids_major_piece_loss`
- `develops_piece`
- `controls_center`
- `improves_king_safety`
- `promotes_or_supports_promotion`
- `best_engine_score`

The first version should prefer correctness over variety. If no clear rule applies, use `best_engine_score`.

## RAG Integration

`rag.py` should accept `teaching_analysis` in `get_advice`.

The prompt should add a section named `已驗證教學分析` containing:

- Ranked candidates with SAN, score, loss, warnings, themes, and short PV.
- Criticality.
- Best move reason.
- Mistake warnings.

The system prompt should instruct the model to:

- Prefer this structured analysis over unsupported chess claims.
- Explain candidate comparisons when available.
- Emphasize critical positions when `criticality` is `sharp` or `only_move`.
- Use warnings to explain common mistakes.
- Avoid inventing tactics or opening names not supported by verified fields.

If no API key is configured, `/get_analysis` should still return `teaching_analysis` so the frontend can show a useful structured summary later.

## Frontend Scope

First implementation can leave the frontend unchanged except for tolerating the new response field. A later UI pass can show:

- Candidate list.
- Best move reason.
- Warning badges.
- Position themes.

This keeps the first engine change testable without coupling it to the current UI redesign diff.

## Testing Plan

Engine tests:

- Candidate list always includes the base best move.
- Best move candidate has `loss_cp == 0`.
- Candidate analysis does not mutate the board.
- A queen-hanging move gets `hangs_major_piece`.
- A mate-in-one position gets a tactics/checkmate-style reason.
- Opening development moves receive `opening_principle` and `development` where applicable.

API tests:

- `/get_analysis` returns `teaching_analysis`.
- `teaching_analysis.candidates` is non-empty for a normal legal position.
- `/make_move` response shape remains unchanged.

RAG tests:

- The prompt includes candidate comparison data.
- The prompt includes warnings and criticality when present.
- Existing opening-name grounding remains enforced.

Regression commands:

```bash
PYTHONPATH=backend .venv/bin/python -m unittest discover -s backend -p 'test_*.py'
cd frontend
npm run lint
npm run build
```

## Non-Goals

- Do not replace the custom engine with Stockfish.
- Do not make `/make_move` slower.
- Do not add speculative move-ordering heuristics in the same change.
- Do not write long natural-language coaching text in `chess_engine.py`.
- Do not require Gemini/API-key availability for structured teaching analysis.

## Risks

- Candidate re-search may consume the time budget. Mitigation: use a bounded candidate count, lower candidate depth, and partial results on timeout.
- Teaching labels may overstate weak evidence. Mitigation: keep labels rule-based, conservative, and tested.
- RAG may still hallucinate. Mitigation: place structured teaching analysis in verified prompt context and keep existing opening-name restrictions.
- Existing dirty frontend changes may obscure review. Mitigation: first implementation should focus on backend/API/RAG and avoid UI coupling.

## Acceptance Criteria

The design is implemented when:

- `/get_analysis` returns a stable `teaching_analysis` object.
- Candidate comparison includes SAN, score, loss, PV, warnings, and themes.
- RAG receives and prioritizes the structured teaching evidence.
- `/make_move` behavior and response shape remain compatible.
- Backend tests, frontend lint, and frontend build pass.
