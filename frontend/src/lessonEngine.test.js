import { describe, expect, it } from "vitest";

import {
  buildLessonChallenges,
  findAcceptedMove,
  scoreLessonAttempt
} from "./lessonEngine";

describe("lesson challenge normalization", () => {
  it("turns a legacy black-side line into learner challenge positions", () => {
    const challenges = buildLessonChallenges({
      side: "black",
      type: "opening",
      goal: "反擊中心",
      moves: ["e4", "c5", "Nf3", "d6"],
      ideas: ["用側翼兵挑戰中心", "完成穩健發展"]
    });

    expect(challenges).toHaveLength(2);
    expect(challenges.map((challenge) => challenge.primaryMove)).toEqual(["c5", "d6"]);
    expect(challenges[0].fen.split(" ")[1]).toBe("b");
  });

  it("accepts multiple reviewed moves with move-specific explanations", () => {
    const challenges = buildLessonChallenges({
      side: "white",
      type: "guided",
      goal: "建立中心",
      startFen: "r1bqk2r/ppp2ppp/2np1n2/2b1p3/2B1P3/3P1N2/PPP2PPP/RNBQ1RK1 w kq - 0 6",
      moves: ["Re1"],
      ideas: ["先讓子力共同支援中心"],
      challengeSteps: {
        0: {
          acceptedMoves: [
            { san: "Re1", explanation: "直接支援 e4。" },
            { san: "c3", explanation: "準備 d4 中心突破。" }
          ]
        }
      }
    });

    expect(challenges[0].acceptedMoves.map((candidate) => candidate.san)).toEqual(["Re1", "c3"]);
    expect(findAcceptedMove(challenges[0], "c3")?.explanation).toBe("準備 d4 中心突破。");
    expect(findAcceptedMove(challenges[0], "Be3")).toBeNull();
  });
});

describe("lesson completion scoring", () => {
  it("combines answer accuracy and hint usage into a pass decision", () => {
    expect(scoreLessonAttempt({ totalSteps: 5, mistakes: 1, hintsUsed: 1 })).toEqual({
      accuracy: 83,
      score: 78,
      passed: true,
      grade: "完成基準",
      passScore: 70
    });
    expect(scoreLessonAttempt({ totalSteps: 1, mistakes: 1, hintsUsed: 1 }).passed).toBe(false);
  });
});

