import { Chess } from "chess.js";
import { describe, expect, it } from "vitest";
import { GUIDE_COLORS, legalMoveStyles, lessonHintGuides, reviewArrows, sanToSquares } from "./boardGuides";

describe("legalMoveStyles", () => {
  it("marks every legal target of the selected piece", () => {
    expect(Object.keys(legalMoveStyles(new Chess(), "g1")).sort()).toEqual(["f3", "h3"]);
    expect(Object.keys(legalMoveStyles(new Chess(), "e2")).sort()).toEqual(["e3", "e4"]);
  });

  it("uses a ring for captures and nothing for empty or blocked squares", () => {
    const game = new Chess("rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2");
    const styles = legalMoveStyles(game, "e4");
    expect(styles.d5.background).not.toEqual(styles.e5.background);
    expect(legalMoveStyles(game, "e5")).toEqual({});
    expect(legalMoveStyles(new Chess(), "a1")).toEqual({});
    expect(legalMoveStyles(new Chess(), null)).toEqual({});
  });
});

describe("lessonHintGuides", () => {
  const challenge = {
    fen: new Chess().fen(),
    acceptedMoves: [{ san: "e4" }, { san: "Nf3" }, { san: "not-a-move" }]
  };

  it("reveals nothing on the board until the second tier", () => {
    expect(lessonHintGuides(challenge, 0)).toEqual({ squareStyles: {}, arrows: [] });
    expect(lessonHintGuides(challenge, 1)).toEqual({ squareStyles: {}, arrows: [] });
  });

  it("lights up the pieces at tier two and draws arrows at tier three", () => {
    const pieces = lessonHintGuides(challenge, 2);
    expect(Object.keys(pieces.squareStyles).sort()).toEqual(["e2", "g1"]);
    expect(pieces.arrows).toEqual([]);
    expect(lessonHintGuides(challenge, 3).arrows).toEqual([
      ["e2", "e4", GUIDE_COLORS.hintArrow],
      ["g1", "f3", GUIDE_COLORS.hintArrow]
    ]);
  });

  it("converts SAN in the challenge position", () => {
    expect(sanToSquares(new Chess().fen(), "Nc3")).toEqual({ from: "b1", to: "c3" });
    expect(sanToSquares(new Chess().fen(), "Nc4")).toBeNull();
  });
});

describe("reviewArrows", () => {
  const rows = [
    { fen: "start" },
    { move: "f2f3", best_move: "e2e4" },
    { move: "e7e5", best_move: "e7e5" }
  ];

  it("shows the recommendation and the move actually played from the displayed position", () => {
    const guide = reviewArrows(rows, 0);
    expect(guide.arrows).toEqual([
      ["e2", "e4", GUIDE_COLORS.bestArrow],
      ["f2", "f3", GUIDE_COLORS.playedArrow]
    ]);
    expect(guide.sameMove).toBe(false);
  });

  it("draws one arrow when the player found the recommendation, none at the end", () => {
    const guide = reviewArrows(rows, 1);
    expect(guide.arrows).toEqual([["e7", "e5", GUIDE_COLORS.bestArrow]]);
    expect(guide.sameMove).toBe(true);
    expect(reviewArrows(rows, 2).arrows).toEqual([]);
  });
});
