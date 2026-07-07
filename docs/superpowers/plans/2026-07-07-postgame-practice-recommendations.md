# Postgame Practice Recommendations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic postgame practice recommendations that route users from review mistakes into existing training lessons.

**Architecture:** Keep the recommendation engine as pure frontend functions in `frontend/src/App.jsx` because the current lessons are frontend constants and `/analyze_full` already returns the needed review data. Render a compact recommendation section inside the existing analysis card.

**Tech Stack:** React, Vite, chess.js, existing CSS.

## Global Constraints

- Do not add backend endpoints or dependencies.
- Do not expand the lesson catalog in this task.
- Recommendations must be deterministic and based on `analysisData`.
- The feature must work when the user has only the existing seven lessons.

---

### Task 1: Lesson Tags And Recommendation Helpers

**Files:**
- Modify: `frontend/src/App.jsx`

**Interfaces:**
- Produces: `getPracticeRecommendations(analysisData, humanColor, lessons)` returning `{ weaknesses, recommendations }`.
- Produces: lessons with `tags: string[]`.

- [ ] Add tags to each `TRAINING_LESSONS` item.
- [ ] Add helper functions near the lesson constants:
  - `getMovePhase(item)`
  - `tagsForReviewMove(item)`
  - `getPracticeRecommendations(analysisData, humanColor, lessons)`
- [ ] Confirm helper logic only considers the human player's moves.

### Task 2: Review UI

**Files:**
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/index.css`

**Interfaces:**
- Consumes: `practiceRecommendations` from Task 1.
- Produces: a "推薦練習" section inside the review analysis card.

- [ ] Compute `practiceRecommendations` in `App`.
- [ ] Add `startRecommendedLesson(lessonId)` that calls `resetTraining(lessonId)` and switches `appMode` to `training`.
- [ ] Render up to two recommended lessons with phase, variation, reason text, and a button.
- [ ] Style the section with compact cards consistent with current UI.

### Task 3: Verification

**Files:**
- No code files.

**Validation commands:**
- `npm run lint` in `frontend`
- `npm run build` in `frontend`
- `PYTHONPATH=backend .venv/bin/python -m unittest discover -s backend -p 'test_*.py'`
- `PYTHONPATH=backend .venv/bin/python backend/teaching_benchmark.py`
- `git diff --check`
