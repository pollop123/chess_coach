import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { OpeningTrainingPanel } from "./App";

const BASE_LESSON = {
  id: "base",
  phase: "opening",
  type: "opening",
  side: "white",
  difficulty: 1,
  variation: "基礎課",
  opening: "Course V2",
  goal: "理解中心控制",
  ideas: ["先判斷中心，再選候選著。"]
};

const ADVANCED_LESSON = {
  ...BASE_LESSON,
  id: "advanced",
  difficulty: 2,
  variation: "進階課",
  prerequisites: ["base"]
};

function renderPanel(overrides = {}) {
  const callbacks = {
    onSelectPhase: vi.fn(),
    onSelectLesson: vi.fn(),
    onHint: vi.fn(),
    onReset: vi.fn(),
    onAdvance: vi.fn(),
    onRetryMissed: vi.fn(),
    onNext: vi.fn(),
    onBack: vi.fn()
  };
  const props = {
    phases: [{ id: "opening", label: "開局" }],
    trainingPhase: "opening",
    lessons: [BASE_LESSON, ADVANCED_LESSON],
    allLessons: [BASE_LESSON, ADVANCED_LESSON],
    learningProgress: { version: 2, lessons: {} },
    selectedLesson: BASE_LESSON,
    selectedLessonId: BASE_LESSON.id,
    feedback: { tone: "warn", text: "這一題可以再想一次。" },
    history: ["c3"],
    expectedMove: "c3",
    challenge: {
      prompt: "如何穩固中心？",
      acceptedMoves: [{ san: "c3" }, { san: "d3" }]
    },
    stepNumber: 1,
    totalSteps: 1,
    stepSolved: true,
    progressPercentage: 100,
    complete: true,
    mistakes: 1,
    hints: 0,
    hintLevel: 0,
    lessonProgress: { mastery: 2, bestScore: 72 },
    attemptResult: {
      score: 50,
      accuracy: 50,
      passScore: 70,
      passed: false,
      grade: "再試一次"
    },
    missedStepsCount: 1,
    nextLesson: null,
    ...callbacks,
    ...overrides
  };

  render(<OpeningTrainingPanel {...props} />);
  return { props, callbacks };
}

describe("OpeningTrainingPanel", () => {
  it("shows a failed score, keeps prerequisites locked, and offers missed-step retry", async () => {
    const user = userEvent.setup();
    const { callbacks } = renderPanel();

    expect(screen.getByRole("region", { name: "課程結業成績" })).toHaveTextContent("本次成績50");
    expect(screen.getByText(/尚未通過/)).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "進階課（需先修）" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: /下一課/ })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "只重練錯題（1）" }));
    expect(callbacks.onRetryMissed).toHaveBeenCalledOnce();
  });

  it("labels a missed-step retry as practice and withholds the next-lesson button", () => {
    renderPanel({
      isRetryDrill: true,
      totalSteps: 2,
      missedStepsCount: 0,
      nextLesson: { id: "advanced", variation: "進階課" },
      attemptResult: {
        score: 100,
        accuracy: 100,
        passScore: 70,
        passed: true,
        grade: "精準掌握"
      }
    });

    expect(screen.getByRole("region", { name: "錯題重練結果" })).toHaveTextContent(
      "這次只重練了 2 題錯題，不會計入結業成績或熟練度。"
    );
    expect(screen.queryByRole("region", { name: "課程結業成績" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /下一課/ })).not.toBeInTheDocument();
  });
});
