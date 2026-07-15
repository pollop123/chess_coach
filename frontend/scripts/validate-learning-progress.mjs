import {
  buildLearningPlan,
  createEmptyLearningProgress,
  getLearningStats,
  getLessonProgress,
  isLessonDue,
  loadLearningProgress,
  recordLessonResult,
  saveLearningProgress
} from "../src/learningProgress.js";

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

const lessons = [
  { id: "opening", difficulty: 1 },
  { id: "tactics", difficulty: 2 },
  { id: "endgame", difficulty: 2 }
];
const firstPracticeAt = new Date("2026-07-01T00:00:00.000Z");
let progress = createEmptyLearningProgress();

progress = recordLessonResult(progress, "opening", {
  completed: true,
  mistakes: 0,
  hintsUsed: 0
}, firstPracticeAt);

let opening = getLessonProgress(progress, "opening");
assert(opening.mastery === 2, "first-try completion should add two mastery levels");
assert(opening.firstTryCompletions === 1, "first-try completion should be tracked");
assert(opening.nextReviewAt === "2026-07-04T00:00:00.000Z", "mastery two should schedule a three-day review");
assert(isLessonDue(progress, "opening", new Date("2026-07-04T00:00:00.000Z")), "lesson should become due on schedule");

progress = recordLessonResult(progress, "opening", {
  completed: true,
  mistakes: 2,
  hintsUsed: 1
}, new Date("2026-07-04T00:00:00.000Z"));
opening = getLessonProgress(progress, "opening");
assert(opening.mastery === 3, "assisted completion should add one mastery level");
assert(opening.totalMistakes === 2 && opening.totalHints === 1, "attempt details should accumulate");

const stats = getLearningStats(progress, lessons, new Date("2026-07-05T00:00:00.000Z"));
assert(stats.completed === 1 && stats.started === 1, "learning stats should count completed and started lessons");

const plan = buildLearningPlan(
  lessons,
  progress,
  [lessons[1]],
  new Date("2026-07-05T00:00:00.000Z")
);
assert(plan[0].lesson.id === "tactics", "review recommendation should outrank unseen fallback lessons");
assert(plan[0].reason.includes("最近一盤"), "recommendation should explain its source");

const memoryStorage = {
  value: null,
  getItem() { return this.value; },
  setItem(_key, value) { this.value = value; }
};
saveLearningProgress(progress, memoryStorage);
assert(loadLearningProgress(memoryStorage).lessons.opening.mastery === 3, "saved progress should round-trip");

console.log("Validated learning progress, mastery, spaced review, and recommendation routing.");
