import { Chess } from "chess.js";

export const GUIDE_COLORS = {
  selected: "rgba(255,209,102,0.92)",
  hintPiece: "rgba(255,209,102,0.78)",
  hintArrow: "rgb(255,170,0)",
  bestArrow: "rgb(46,160,90)",
  playedArrow: "rgb(214,69,65)"
};

const MOVE_DOT = "radial-gradient(circle, rgba(20,40,30,0.32) 24%, transparent 26%)";
const CAPTURE_RING = "radial-gradient(circle, transparent 58%, rgba(20,40,30,0.32) 60%)";

/** Dots on empty targets and rings on captures, so beginners see how a piece moves. */
export function legalMoveStyles(game, square) {
  if (!game || !square) return {};
  let moves;
  try {
    moves = game.moves({ square, verbose: true });
  } catch {
    return {};
  }
  const styles = {};
  for (const move of moves) {
    // Promotions list the same target square once per piece.
    styles[move.to] = { background: move.captured ? CAPTURE_RING : MOVE_DOT };
  }
  return styles;
}

export function sanToSquares(fen, san) {
  try {
    const move = new Chess(fen).move(san);
    return move ? { from: move.from, to: move.to } : null;
  } catch {
    return null;
  }
}

function uciToSquares(uci) {
  return typeof uci === "string" && /^[a-h][1-8][a-h][1-8]/.test(uci)
    ? { from: uci.slice(0, 2), to: uci.slice(2, 4) }
    : null;
}

/**
 * Lesson hint tiers: 1 = concept text only, 2 = light up the pieces that can
 * make an accepted move, 3 = also draw the accepted moves as arrows.
 */
export function lessonHintGuides(challenge, level) {
  if (!challenge || level < 2) return { squareStyles: {}, arrows: [] };
  const moves = (challenge.acceptedMoves || [])
    .map((candidate) => sanToSquares(challenge.fen, candidate.san))
    .filter(Boolean);
  const squareStyles = {};
  for (const { from } of moves) {
    squareStyles[from] = { boxShadow: `inset 0 0 0 4px ${GUIDE_COLORS.hintPiece}` };
  }
  const arrows = level >= 3 ? moves.map(({ from, to }) => [from, to, GUIDE_COLORS.hintArrow]) : [];
  return { squareStyles, arrows };
}

/**
 * Row i holds the position after move i; row i + 1 holds the move played from
 * it and the engine's recommendation for that same position.
 */
export function reviewArrows(analysisData, index) {
  const next = analysisData?.[index + 1];
  if (!next) return { arrows: [], best: null, played: null };
  const best = uciToSquares(next.best_move);
  const played = uciToSquares(next.move);
  const arrows = [];
  if (best) arrows.push([best.from, best.to, GUIDE_COLORS.bestArrow]);
  if (played && !(best && best.from === played.from && best.to === played.to)) {
    arrows.push([played.from, played.to, GUIDE_COLORS.playedArrow]);
  }
  return { arrows, best, played, sameMove: Boolean(best && played && arrows.length === 1) };
}
