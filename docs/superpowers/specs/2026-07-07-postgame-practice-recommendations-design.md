# Postgame Practice Recommendations Design

## Goal

After a player analyzes a completed game, show a small set of recommended existing training lessons based on the player's largest mistakes.

## Scope

This is an MVP recommendation layer over the current frontend training lessons and full-game analysis. It does not add a new course system, database table, LLM prompt, or backend endpoint.

## User Experience

When `analysisData` is available in review mode, the analysis panel should show a "推薦練習" section. The section summarizes the main weakness categories found in the player's own inaccurate, mistaken, or blunder moves, then shows up to two matching lessons. Each recommendation has a button that switches to training mode and loads that lesson.

If there are no clear mistakes, the section should recommend one low-risk default lesson from the current phase mix and say the game did not reveal a major recurring weakness.

## Recommendation Rules

Each `TRAINING_LESSON` gets a `tags` array. Tags are coarse and reusable, such as `opening`, `development`, `tactics`, `king_safety`, `endgame`, and `promotion`.

Weakness detection uses existing `analysisData` fields:

- Only consider moves by the human player.
- Prioritize `classification` values `blunder`, `mistake`, and `inaccuracy`.
- Add `tactics` and `calculation` when `cp_loss >= 150`.
- Add `king_safety` when `mate_threat` is true.
- Add `opening` and `development` for early mistakes.
- Add `endgame` for low-material or late-game mistakes.
- Add `promotion` if a mistake has a very large centipawn loss in an endgame-like position.

Lesson ranking is deterministic. Score a lesson by matching lesson tags against detected weakness tags, with a small bonus for matching the lesson phase. Show the top two unique lessons.

## UI Constraints

Keep the UI inside the existing analysis panel. Do not create a landing page or new route. The section should be compact, scan-friendly, and consistent with the current card styling.

## Validation

Run frontend lint and build. Run backend tests to make sure the existing API and engine work remain stable.
