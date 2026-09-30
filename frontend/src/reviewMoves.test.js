import { describe, expect, it } from "vitest";
import { criticalMoves, movePairs, reviewMoveList } from "./reviewMoves";

const rows = [
  { move_number: 0 },
  { move_number: 1, side_to_move: "white", classification: "good" },
  { move_number: 2, side_to_move: "black", classification: "inaccuracy" },
  { move_number: 3, side_to_move: "white", classification: "blunder" },
  { move_number: 4, side_to_move: "black", classification: "mistake" },
  { move_number: 5, side_to_move: "white" },
];
const sans = ["e4", "e5", "Qh5", "Nc6", "Qxf7+"];

describe("reviewMoveList", () => {
  it("labels moves with move numbers and marks, keeping analysis indexes", () => {
    const moves = reviewMoveList(rows, sans);
    expect(moves.map((move) => `${move.label}${move.mark}`)).toEqual([
      "1. e4", "1... e5?!", "2. Qh5??", "2... Nc6?", "3. Qxf7+",
    ]);
    expect(moves.map((move) => move.index)).toEqual([1, 2, 3, 4, 5]);
  });

  it("lists only blunders and mistakes as critical", () => {
    expect(criticalMoves(reviewMoveList(rows, sans)).map((move) => move.san)).toEqual(["Qh5", "Nc6"]);
  });

  it("pairs white and black moves per move number, including a trailing white move", () => {
    const pairs = movePairs(reviewMoveList(rows, sans));
    expect(pairs.map((pair) => [pair.number, pair.white?.san ?? null, pair.black?.san ?? null])).toEqual([
      [1, "e4", "e5"], [2, "Qh5", "Nc6"], [3, "Qxf7+", null],
    ]);
  });

  it("falls back to ply parity when a row has no side", () => {
    const moves = reviewMoveList([{}, {}, {}], ["d4", "d5"]);
    expect(moves.map((move) => move.label)).toEqual(["1. d4", "1... d5"]);
  });
});
