import { Chess } from "chess.js";

function normalizeAcceptedMove(candidate, fallbackExplanation) {
  if (typeof candidate === "string") {
    return { san: candidate, explanation: fallbackExplanation };
  }
  return {
    san: candidate?.san || "",
    explanation: candidate?.explanation || fallbackExplanation
  };
}

export function buildLessonChallenges(lesson) {
  if (!lesson || !Array.isArray(lesson.moves)) return [];

  const board = lesson.startFen ? new Chess(lesson.startFen) : new Chess();
  const learnerTurn = lesson.side === "black" ? "b" : "w";
  const challenges = [];
  let learnerStepIndex = 0;

  lesson.moves.forEach((san, plyIndex) => {
    if (board.turn() === learnerTurn) {
      const override = lesson.challengeSteps?.[learnerStepIndex] || {};
      const fallbackExplanation = lesson.ideas?.[
        Math.min(learnerStepIndex, Math.max(0, (lesson.ideas?.length || 1) - 1))
      ] || lesson.goal;
      // 主線那一手預設一定是可接受答案，課程改動後才不會出現無解的題目。
      // 陷阱課要把主線標成錯誤答案時，必須明確宣告 rejectsMainline。
      const rejectsMainline = Boolean(override.rejectsMainline);
      const configuredMoves = (override.acceptedMoves || [san])
        .map((candidate) => normalizeAcceptedMove(candidate, fallbackExplanation))
        .filter((candidate) => candidate.san && !(rejectsMainline && candidate.san === san));
      const acceptedMoves = rejectsMainline || configuredMoves.some((candidate) => candidate.san === san)
        ? configuredMoves
        : [{ san, explanation: fallbackExplanation }, ...configuredMoves];

      challenges.push({
        index: learnerStepIndex,
        sourcePly: plyIndex,
        fen: board.fen(),
        mainlineMove: san,
        rejectsMainline,
        primaryMove: rejectsMainline ? (acceptedMoves[0]?.san || san) : san,
        prompt: override.prompt || (lesson.type === "puzzle" ? "找出局面的最佳手。" : "運用本課觀念選出合適走法。"),
        hints: [
          override.hints?.[0] || fallbackExplanation,
          override.hints?.[1] || `可考慮：${acceptedMoves.map((candidate) => candidate.san).join("、")}`
        ],
        acceptedMoves
      });
      learnerStepIndex += 1;
    }

    board.move(san);
  });

  return challenges;
}

export function findAcceptedMove(challenge, san) {
  return challenge?.acceptedMoves?.find((candidate) => candidate.san === san) || null;
}

export function scoreLessonAttempt({ totalSteps, mistakes = 0, hintsUsed = 0, passScore = 70 }) {
  const safeSteps = Math.max(1, Number(totalSteps) || 1);
  const safeMistakes = Math.max(0, Number(mistakes) || 0);
  const safeHints = Math.max(0, Number(hintsUsed) || 0);
  const accuracy = Math.round((safeSteps / (safeSteps + safeMistakes)) * 100);
  const score = Math.max(0, Math.round(accuracy - safeHints * 5));
  const passed = score >= passScore;
  const grade = score >= 95 ? "精準掌握" : score >= 80 ? "穩定通過" : passed ? "完成基準" : "建議重練";

  return { accuracy, score, passed, grade, passScore };
}

