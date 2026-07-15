export const LEARNING_PROGRESS_STORAGE_KEY = "chess-coach-learning-progress-v1";

const REVIEW_INTERVAL_DAYS = [0, 1, 3, 7, 14, 30];

export function createEmptyLearningProgress() {
  return { version: 1, lessons: {} };
}

export function loadLearningProgress(storage) {
  try {
    const targetStorage = storage === undefined ? globalThis.localStorage : storage;
    if (!targetStorage) return createEmptyLearningProgress();

    const raw = targetStorage.getItem(LEARNING_PROGRESS_STORAGE_KEY);
    if (!raw) return createEmptyLearningProgress();
    const parsed = JSON.parse(raw);
    if (parsed?.version !== 1 || !parsed.lessons || typeof parsed.lessons !== "object") {
      return createEmptyLearningProgress();
    }
    return parsed;
  } catch {
    return createEmptyLearningProgress();
  }
}

export function saveLearningProgress(progress, storage) {
  try {
    const targetStorage = storage === undefined ? globalThis.localStorage : storage;
    if (!targetStorage) return;

    targetStorage.setItem(LEARNING_PROGRESS_STORAGE_KEY, JSON.stringify(progress));
  } catch {
    // Learning remains usable when storage is unavailable or full.
  }
}

export function getLessonProgress(progress, lessonId) {
  return progress.lessons[lessonId] || {
    attempts: 0,
    completions: 0,
    firstTryCompletions: 0,
    totalMistakes: 0,
    totalHints: 0,
    mastery: 0,
    lastPracticedAt: null,
    nextReviewAt: null
  };
}

export function recordLessonResult(progress, lessonId, result, now = new Date()) {
  const previous = getLessonProgress(progress, lessonId);
  const completed = Boolean(result.completed);
  const mistakes = Math.max(0, Number(result.mistakes) || 0);
  const hintsUsed = Math.max(0, Number(result.hintsUsed) || 0);
  const firstTry = completed && mistakes === 0 && hintsUsed === 0;

  let mastery = previous.mastery || 0;
  if (completed && firstTry) mastery += 2;
  else if (completed) mastery += 1;
  else mastery -= 1;
  mastery = Math.max(0, Math.min(5, mastery));

  const reviewDate = new Date(now);
  reviewDate.setDate(reviewDate.getDate() + REVIEW_INTERVAL_DAYS[mastery]);

  return {
    ...progress,
    lessons: {
      ...progress.lessons,
      [lessonId]: {
        attempts: previous.attempts + 1,
        completions: previous.completions + (completed ? 1 : 0),
        firstTryCompletions: previous.firstTryCompletions + (firstTry ? 1 : 0),
        totalMistakes: previous.totalMistakes + mistakes,
        totalHints: previous.totalHints + hintsUsed,
        mastery,
        lastPracticedAt: now.toISOString(),
        nextReviewAt: reviewDate.toISOString()
      }
    }
  };
}

export function isLessonDue(progress, lessonId, now = new Date()) {
  const lessonProgress = getLessonProgress(progress, lessonId);
  if (!lessonProgress.nextReviewAt) return false;
  return new Date(lessonProgress.nextReviewAt).getTime() <= now.getTime();
}

export function getLearningStats(progress, lessons, now = new Date()) {
  const started = lessons.filter((lesson) => getLessonProgress(progress, lesson.id).attempts > 0).length;
  const completed = lessons.filter((lesson) => getLessonProgress(progress, lesson.id).completions > 0).length;
  const due = lessons.filter((lesson) => isLessonDue(progress, lesson.id, now)).length;
  const masteryTotal = lessons.reduce(
    (sum, lesson) => sum + getLessonProgress(progress, lesson.id).mastery,
    0
  );

  return {
    started,
    completed,
    due,
    masteryPercent: lessons.length ? Math.round((masteryTotal / (lessons.length * 5)) * 100) : 0
  };
}

export function buildLearningPlan(lessons, progress, reviewRecommendations = [], now = new Date()) {
  const recommendationIds = new Set(reviewRecommendations.map((lesson) => lesson.id));
  const ranked = lessons.map((lesson, index) => {
    const lessonProgress = getLessonProgress(progress, lesson.id);
    const due = isLessonDue(progress, lesson.id, now);
    const reviewMatch = recommendationIds.has(lesson.id);
    const unseen = lessonProgress.attempts === 0;
    const score = (due ? 100 : 0)
      + (reviewMatch ? 70 : 0)
      + (unseen ? 25 : 0)
      + (5 - lessonProgress.mastery) * 4
      - index / 100;

    let reason = "繼續建立完整棋局觀念";
    if (due && reviewMatch) reason = "這盤暴露的弱點，而且已到複習時間";
    else if (due) reason = "已到間隔複習時間";
    else if (reviewMatch) reason = "根據最近一盤的失誤推薦";
    else if (unseen) reason = "尚未完成的新課程";
    else if (lessonProgress.mastery < 3) reason = "熟練度仍需加強";

    return { lesson, reason, score };
  });

  return ranked
    .sort((a, b) => b.score - a.score || a.lesson.id.localeCompare(b.lesson.id))
    .slice(0, 3);
}

export function getNextLesson(lessons, currentLessonId, progress) {
  if (!lessons.length) return null;
  const currentIndex = lessons.findIndex((lesson) => lesson.id === currentLessonId);
  const ordered = [
    ...lessons.slice(currentIndex + 1),
    ...lessons.slice(0, Math.max(0, currentIndex + 1))
  ];
  return ordered.find((lesson) => getLessonProgress(progress, lesson.id).completions === 0)
    || ordered[0]
    || lessons[0];
}
