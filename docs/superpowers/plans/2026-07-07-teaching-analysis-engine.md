# Teaching Analysis Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add structured teaching analysis to `/get_analysis` while preserving `/make_move` speed and compatibility.

**Architecture:** Add a backend-only teaching analysis layer in `backend/chess_engine.py` that compares candidate moves with existing engine primitives. Thread the resulting `teaching_analysis` object through `backend/api.py` and into `backend/rag.py` as verified prompt evidence.

**Tech Stack:** Python, python-chess, FastAPI, unittest, existing React/Vite frontend.

## Global Constraints

- Do not change `/make_move` behavior or response shape.
- Do not replace the custom engine with Stockfish.
- Do not require Gemini/API-key availability for structured teaching analysis.
- Keep teaching labels rule-based and conservative.
- Preserve existing dirty worktree changes outside this feature.

---

### Task 1: Engine Teaching Analysis

**Files:**
- Modify: `backend/chess_engine.py`
- Create: `backend/test_teaching_analysis.py`

**Interfaces:**
- Consumes: `get_analysis(board, ...)`, `order_moves(board)`, `minimax(...)`, `major_piece_loss_after_move(board, move)`, `format_evaluation(score)`, `detect_game_phase(board)`.
- Produces: `get_teaching_analysis(board, base_analysis, candidate_count=5, depth=None, time_limit=None) -> dict`.

- [x] **Step 1: Write failing engine tests**

Add tests for candidate inclusion, best move `loss_cp == 0`, board preservation, queen-hang warnings, and mate/checkmate reason.

- [x] **Step 2: Implement minimal engine function**

Add helper functions for move reasons, themes, warnings, candidate search, criticality, and top-level `get_teaching_analysis`.

- [x] **Step 3: Run backend tests**

Run: `PYTHONPATH=backend .venv/bin/python -m unittest backend.test_teaching_analysis`
Expected: all tests pass.

---

### Task 2: API Integration

**Files:**
- Modify: `backend/api.py`
- Modify: `backend/test_api_endpoints.py`

**Interfaces:**
- Consumes: `chess_engine.get_teaching_analysis(board, analysis, time_limit=...)`.
- Produces: `/get_analysis` response field `teaching_analysis`.

- [x] **Step 1: Write failing API test**

Assert `/get_analysis` contains `teaching_analysis.candidates` and `/make_move` omits `teaching_analysis`.

- [x] **Step 2: Add API response field**

Call `get_teaching_analysis` after base analysis, pass the result to RAG and to the JSON response.

- [x] **Step 3: Run API tests**

Run: `PYTHONPATH=backend .venv/bin/python -m unittest backend.test_api_endpoints`
Expected: all tests pass.

---

### Task 3: RAG Grounding

**Files:**
- Modify: `backend/rag.py`
- Modify: `backend/test_rag_grounding.py`

**Interfaces:**
- Consumes: `teaching_analysis` dict from API/engine.
- Produces: verified prompt section `已驗證教學分析`.

- [x] **Step 1: Write failing RAG prompt test**

Assert generated prompt contains candidate SAN, loss, warnings, themes, criticality, and best move reason.

- [x] **Step 2: Extend RAG prompt construction**

Add optional `teaching_analysis` parameter to `get_advice`, format it into a compact verified section, and pass it from API.

- [x] **Step 3: Run RAG tests**

Run: `PYTHONPATH=backend .venv/bin/python -m unittest backend.test_rag_grounding`
Expected: all tests pass.

---

### Task 4: Full Regression

**Files:**
- Existing backend and frontend files only.

**Interfaces:**
- Consumes: all tasks above.
- Produces: verified working feature.

- [x] **Step 1: Run backend regression**

Run: `PYTHONPATH=backend .venv/bin/python -m unittest discover -s backend -p 'test_*.py'`
Expected: all tests pass.

- [x] **Step 2: Run frontend checks**

Run from `frontend/`: `npm run lint` and `npm run build`
Expected: both pass. Existing Vite chunk warning is acceptable.

- [x] **Step 3: Run diff check**

Run: `git diff --check`
Expected: no output.
