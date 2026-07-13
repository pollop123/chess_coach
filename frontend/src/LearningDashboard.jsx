import { getLessonProgress } from "./learningProgress";

const LESSON_TYPE_LABELS = {
  opening: "主線課",
  puzzle: "局面題",
  guided: "引導課",
  endgame: "殘局課"
};

export function LearningDashboard({ phases, lessons, progress, stats, plan, onStartLesson, onReturnToGame }) {
  return (
    <main className="learning-dashboard">
      <section className="learning-hero">
        <div>
          <div className="panel-kicker">Learning Area</div>
          <h2>學習專區</h2>
          <p>從最近弱點開始，練習、複習，再回到實戰驗證。</p>
        </div>
        <button className="btn btn-inverse" onClick={onReturnToGame}>返回對局</button>
      </section>

      <section className="learning-stat-grid" aria-label="學習進度摘要">
        <LearningStat label="已完成" value={`${stats.completed}/${lessons.length}`} />
        <LearningStat label="待複習" value={stats.due} />
        <LearningStat label="已開始" value={stats.started} />
        <LearningStat label="總熟練度" value={`${stats.masteryPercent}%`} />
      </section>

      <section className="learning-section">
        <div className="learning-section__heading">
          <div>
            <div className="panel-kicker">今日安排</div>
            <h3>推薦先練這三堂</h3>
          </div>
          <p>優先順序綜合復盤弱點、複習時間與熟練度。</p>
        </div>
        <div className="learning-plan-grid">
          {plan.map(({ lesson, reason }, index) => (
            <LessonCard
              key={lesson.id}
              lesson={lesson}
              lessonProgress={getLessonProgress(progress, lesson.id)}
              reason={reason}
              rank={index + 1}
              onStart={() => onStartLesson(lesson.id)}
            />
          ))}
        </div>
      </section>

      <section className="learning-section">
        <div className="learning-section__heading">
          <div>
            <div className="panel-kicker">課程地圖</div>
            <h3>依棋局階段學習</h3>
          </div>
          <p>主線課建立計畫，引導課練觀念，局面題訓練辨識與計算。</p>
        </div>

        <div className="curriculum-groups">
          {phases.map((phase) => {
            const phaseLessons = lessons.filter((lesson) => lesson.phase === phase.id);
            const completed = phaseLessons.filter(
              (lesson) => getLessonProgress(progress, lesson.id).completions > 0
            ).length;
            return (
              <section className="curriculum-group" key={phase.id}>
                <div className="curriculum-group__header">
                  <div>
                    <h4>{phase.label}</h4>
                    <span>{completed}/{phaseLessons.length} 堂完成</span>
                  </div>
                  <div className="mini-progress" aria-label={`${phase.label}進度`}>
                    <div style={{ width: `${phaseLessons.length ? (completed / phaseLessons.length) * 100 : 0}%` }} />
                  </div>
                </div>
                <div className="curriculum-list">
                  {phaseLessons.map((lesson) => (
                    <CurriculumRow
                      key={lesson.id}
                      lesson={lesson}
                      lessonProgress={getLessonProgress(progress, lesson.id)}
                      onStart={() => onStartLesson(lesson.id)}
                    />
                  ))}
                </div>
              </section>
            );
          })}
        </div>
      </section>
    </main>
  );
}

function LearningStat({ label, value }) {
  return (
    <div className="learning-stat">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function LessonCard({ lesson, lessonProgress, reason, rank, onStart }) {
  return (
    <article className="lesson-card">
      <div className="lesson-card__topline">
        <span className="lesson-rank">{rank}</span>
        <span className="mastery-badge">熟練度 {lessonProgress.mastery}/5</span>
      </div>
      <div className="lesson-chip-row lesson-chip-row--light">
        <span>{LESSON_TYPE_LABELS[lesson.type] || "課程"}</span>
        <span>{lesson.side === "black" ? "執黑" : "執白"}</span>
        <span>難度 {lesson.difficulty}</span>
      </div>
      <h4>{lesson.variation}</h4>
      <small>{lesson.opening}</small>
      <p>{lesson.goal}</p>
      <div className="recommendation-reason">{reason}</div>
      <button className="btn btn-primary" onClick={onStart}>
        {lessonProgress.attempts ? "繼續練習" : "開始課程"}
      </button>
    </article>
  );
}

function CurriculumRow({ lesson, lessonProgress, onStart }) {
  const completed = lessonProgress.completions > 0;
  return (
    <button className="curriculum-row" onClick={onStart}>
      <span className={`curriculum-status ${completed ? "is-complete" : ""}`} aria-hidden="true">
        {completed ? "✓" : lesson.difficulty}
      </span>
      <span className="curriculum-copy">
        <strong>{lesson.variation}</strong>
        <small>{LESSON_TYPE_LABELS[lesson.type] || "課程"} · {lesson.side === "black" ? "執黑" : "執白"}</small>
      </span>
      <span className="curriculum-mastery">{lessonProgress.mastery}/5</span>
    </button>
  );
}
