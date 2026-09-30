export const MOVE_MARKS = { blunder: "??", mistake: "?", inaccuracy: "?!" };
export const CLASSIFICATION_LABELS = { blunder: "大失誤", mistake: "錯誤", inaccuracy: "稍不精確" };

/**
 * One entry per played move. Row 0 of the review is the starting position and
 * row i is the position after move i, so move i lives at analysisData index i.
 */
export function reviewMoveList(analysisData, sanHistory) {
  const moves = [];
  for (let index = 1; index < analysisData.length; index += 1) {
    const row = analysisData[index] || {};
    const ply = row.move_number ?? index;
    const color = row.side_to_move === "black" || row.side_to_move === "white"
      ? row.side_to_move
      : (ply % 2 === 1 ? "white" : "black");
    const moveNumber = Math.ceil(ply / 2);
    const san = sanHistory[index - 1] || row.move || "?";
    const classification = row.classification || null;
    moves.push({
      index,
      ply,
      moveNumber,
      color,
      san,
      label: color === "white" ? `${moveNumber}. ${san}` : `${moveNumber}... ${san}`,
      mark: MOVE_MARKS[classification] || "",
      classification,
    });
  }
  return moves;
}

export function criticalMoves(moves) {
  return moves.filter((move) => move.classification === "blunder" || move.classification === "mistake");
}

/** Rows of [moveNumber, whiteMove, blackMove] for a two-column move list. */
export function movePairs(moves) {
  const pairs = [];
  for (const move of moves) {
    const last = pairs[pairs.length - 1];
    if (move.color === "white" || !last || last.number !== move.moveNumber || last.black) {
      pairs.push({ number: move.moveNumber, white: move.color === "white" ? move : null, black: move.color === "black" ? move : null });
    } else {
      last.black = move;
    }
  }
  return pairs;
}
