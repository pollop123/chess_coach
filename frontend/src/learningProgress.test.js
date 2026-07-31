import { describe, expect, it } from "vitest";

import {
  LEARNING_PROGRESS_STORAGE_KEY,
  buildLearningPlan,
  createEmptyLearningProgress,
  getLearningStats,
  getNextLesson,
  isLessonDue,
  loadLearningProgress,
  recordLessonResult,
  saveLearningProgress
} from "./learningProgress";

const NOW = new Date("2026-01-15T12:00:00.000Z");

const LESSONS = [
  { id: "opening", phase: "opening" },
  { id: "middlegame", phase: "middlegame" },
  { id: "endgame", phase: "endgame" },
  { id: "tactics", phase: "middlegame" }
];

function lessonProgress(overrides = {}) {
  return {
    attempts: 1,
    completions: 1,
    firstTryCompletions: 0,
    totalMistakes: 1,
    totalHints: 0,
    mastery: 2,
    lastPracticedAt: "2026-01-10T12:00:00.000Z",
    nextReviewAt: "2026-01-18T12:00:00.000Z",
    ...overrides
  };
}

describe("learning progress persistence", () => {
  it("round-trips a valid progress record through the supplied storage", () => {
    const values = new Map();
    const storage = {
      getItem: (key) => values.get(key) ?? null,
      setItem: (key, value) => values.set(key, value)
    };
    const progress = {
      version: 1,
      lessons: { opening: lessonProgress() }
    };

    saveLearningProgress(progress, storage);

    expect(values.has(LEARNING_PROGRESS_STORAGE_KEY)).toBe(true);
    expect(loadLearningProgress(storage)).toEqual(progress);
  });

  it.each([
    ["missing data", null],
    ["malformed JSON", "{"],
    ["unsupported version", JSON.stringify({ version: 2, lessons: {} })],
    ["missing lesson map", JSON.stringify({ version: 1 })]
  ])("falls back to empty progress for %s", (_label, storedValue) => {
    const storage = { getItem: () => storedValue };

    expect(loadLearningProgress(storage)).toEqual(createEmptyLearningProgress());
  });
});

describe("recordLessonResult", () => {
  it("rewards a first-try completion and schedules the matching review interval", () => {
    const original = createEmptyLearningProgress();

    const updated = recordLessonResult(
      original,
      "opening",
      { completed: true, mistakes: 0, hintsUsed: 0 },
      NOW
    );

    expect(updated.lessons.opening).toMatchObject({
      attempts: 1,
      completions: 1,
      firstTryCompletions: 1,
      totalMistakes: 0,
      totalHints: 0,
      mastery: 2,
      lastPracticedAt: "2026-01-15T12:00:00.000Z",
      nextReviewAt: "2026-01-18T12:00:00.000Z"
    });
    expect(original).toEqual(createEmptyLearningProgress());
  });

  it("reduces mastery after an incomplete attempt without going below zero", () => {
    const progress = {
      version: 1,
      lessons: {
        endgame: lessonProgress({ mastery: 1, completions: 0 })
      }
    };

    const updated = recordLessonResult(
      progress,
      "endgame",
      { completed: false, mistakes: 2, hintsUsed: 1 },
      NOW
    );
    const repeatedFailure = recordLessonResult(
      updated,
      "endgame",
      { completed: false, mistakes: 1, hintsUsed: 0 },
      NOW
    );

    expect(updated.lessons.endgame).toMatchObject({
      attempts: 2,
      completions: 0,
      totalMistakes: 3,
      totalHints: 1,
      mastery: 0,
      nextReviewAt: "2026-01-15T12:00:00.000Z"
    });
    expect(repeatedFailure.lessons.endgame.mastery).toBe(0);
  });
});

describe("learning statistics and recommendations", () => {
  const progress = {
    version: 1,
    lessons: {
      opening: lessonProgress({
        mastery: 4,
        nextReviewAt: "2026-01-14T12:00:00.000Z"
      }),
      middlegame: lessonProgress({
        mastery: 2,
        completions: 0,
        nextReviewAt: "2026-01-20T12:00:00.000Z"
      }),
      endgame: lessonProgress({
        mastery: 3,
        nextReviewAt: "2026-01-14T12:00:00.000Z"
      })
    }
  };

  it("counts started, completed, due, and aggregate mastery deterministically", () => {
    expect(isLessonDue(progress, "opening", NOW)).toBe(true);
    expect(isLessonDue(progress, "middlegame", NOW)).toBe(false);
    expect(isLessonDue(progress, "tactics", NOW)).toBe(false);
    expect(getLearningStats(progress, LESSONS, NOW)).toEqual({
      started: 3,
      completed: 2,
      due: 2,
      masteryPercent: 45
    });
  });

  it("prioritizes a due lesson that also matches the latest game review", () => {
    const plan = buildLearningPlan(
      LESSONS,
      progress,
      [LESSONS.find((lesson) => lesson.id === "endgame")],
      NOW
    );

    expect(plan.map(({ lesson }) => lesson.id)).toEqual([
      "endgame",
      "opening",
      "tactics"
    ]);
    expect(plan[0].reason).toBe("這盤暴露的弱點，而且已到複習時間");
    expect(plan[1].reason).toBe("已到間隔複習時間");
    expect(plan[2].reason).toBe("尚未完成的新課程");
  });

  it("selects the next unfinished lesson and wraps around the curriculum", () => {
    expect(getNextLesson(LESSONS, "endgame", progress)?.id).toBe("tactics");

    const tacticsCompleted = {
      ...progress,
      lessons: {
        ...progress.lessons,
        tactics: lessonProgress()
      }
    };
    expect(getNextLesson(LESSONS, "endgame", tacticsCompleted)?.id).toBe("middlegame");
  });
});
