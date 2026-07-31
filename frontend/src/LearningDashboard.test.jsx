import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { LearningDashboard } from "./LearningDashboard";

const PHASES = [
  { id: "opening", label: "開局" },
  { id: "endgame", label: "殘局" }
];

const LESSONS = [
  {
    id: "italian",
    phase: "opening",
    type: "opening",
    side: "white",
    difficulty: 1,
    variation: "義大利開局",
    opening: "Italian Game",
    goal: "完成發展並控制中心"
  },
  {
    id: "rook-endgame",
    phase: "endgame",
    type: "endgame",
    side: "black",
    difficulty: 2,
    variation: "車兵殘局",
    opening: "Rook Endgame",
    goal: "讓王與車保持主動"
  }
];

const PROGRESS = {
  version: 1,
  lessons: {
    italian: {
      attempts: 2,
      completions: 1,
      firstTryCompletions: 0,
      totalMistakes: 1,
      totalHints: 1,
      mastery: 3,
      lastPracticedAt: "2026-01-15T12:00:00.000Z",
      nextReviewAt: "2026-01-22T12:00:00.000Z"
    }
  }
};

const STATS = {
  completed: 1,
  due: 1,
  started: 1,
  masteryPercent: 30
};

const PLAN = [
  {
    lesson: LESSONS[0],
    reason: "已到間隔複習時間"
  },
  {
    lesson: LESSONS[1],
    reason: "根據最近一盤的失誤推薦"
  }
];

function renderDashboard(overrides = {}) {
  const props = {
    phases: PHASES,
    lessons: LESSONS,
    progress: PROGRESS,
    stats: STATS,
    plan: PLAN,
    onStartLesson: vi.fn(),
    onReturnToGame: vi.fn(),
    ...overrides
  };

  render(<LearningDashboard {...props} />);
  return props;
}

describe("LearningDashboard", () => {
  it("shows progress, recommendation reasons, and started/completed lesson states", () => {
    renderDashboard();

    const summary = screen.getByRole("region", { name: "學習進度摘要" });
    expect(within(summary).getByText("1/2")).toBeVisible();
    expect(within(summary).getByText("30%")).toBeVisible();
    expect(screen.getByText("已到間隔複習時間")).toBeVisible();
    expect(screen.getByText("根據最近一盤的失誤推薦")).toBeVisible();
    expect(screen.getByRole("button", { name: "繼續練習" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "開始課程" })).toBeEnabled();
    expect(screen.getByText("1/1 堂完成")).toBeVisible();
    expect(screen.getByText("0/1 堂完成")).toBeVisible();
    expect(screen.getByLabelText("開局進度").firstElementChild).toHaveStyle({ width: "100%" });
    expect(screen.getByLabelText("殘局進度").firstElementChild).toHaveStyle({ width: "0%" });
  });

  it("starts lessons from both the recommendation and curriculum controls", async () => {
    const user = userEvent.setup();
    const { onStartLesson } = renderDashboard();

    await user.click(screen.getByRole("button", { name: "繼續練習" }));
    await user.click(screen.getByRole("button", { name: /車兵殘局/ }));

    expect(onStartLesson).toHaveBeenNthCalledWith(1, "italian");
    expect(onStartLesson).toHaveBeenNthCalledWith(2, "rook-endgame");
  });

  it("returns to the active game from the dashboard", async () => {
    const user = userEvent.setup();
    const { onReturnToGame } = renderDashboard();

    await user.click(screen.getByRole("button", { name: "返回對局" }));

    expect(onReturnToGame).toHaveBeenCalledOnce();
  });
});
