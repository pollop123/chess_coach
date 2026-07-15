import { Chess } from "chess.js";
import { TRAINING_LESSONS } from "../src/trainingLessons.js";

const REQUIRED_PHASES = new Set(["opening", "middlegame", "endgame"]);
const ALLOWED_TYPES = new Set(["opening", "puzzle", "guided", "endgame"]);
const ALLOWED_SIDES = new Set(["white", "black"]);
const seenIds = new Set();
const phaseCounts = new Map();

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

function validatePositionSemantics(board, lessonId, fen) {
  const pieces = board.board().flat().filter(Boolean);
  const whitePieces = pieces.filter((piece) => piece.color === "w");
  const blackPieces = pieces.filter((piece) => piece.color === "b");
  const whiteKings = whitePieces.filter((piece) => piece.type === "k");
  const blackKings = blackPieces.filter((piece) => piece.type === "k");
  const whitePawns = whitePieces.filter((piece) => piece.type === "p");
  const blackPawns = blackPieces.filter((piece) => piece.type === "p");

  assert(whiteKings.length === 1, `${lessonId} must have exactly one white king`);
  assert(blackKings.length === 1, `${lessonId} must have exactly one black king`);
  assert(whitePieces.length <= 16 && blackPieces.length <= 16, `${lessonId} has too many pieces`);
  assert(whitePawns.length <= 8 && blackPawns.length <= 8, `${lessonId} has too many pawns`);
  assert(
    [...whitePawns, ...blackPawns].every((piece) => !/[18]$/.test(piece.square)),
    `${lessonId} has a pawn on the first or eighth rank`
  );

  const movingColor = board.turn();
  const nonMovingKing = movingColor === "w" ? blackKings[0] : whiteKings[0];
  assert(
    !board.isAttacked(nonMovingKing.square, movingColor),
    `${lessonId} is invalid because the non-moving king is already in check`
  );

  const castling = (fen || "").split(" ")[2] || "-";
  const requiredPieces = {
    K: [["e1", "k", "w"], ["h1", "r", "w"]],
    Q: [["e1", "k", "w"], ["a1", "r", "w"]],
    k: [["e8", "k", "b"], ["h8", "r", "b"]],
    q: [["e8", "k", "b"], ["a8", "r", "b"]]
  };
  for (const right of castling === "-" ? [] : castling) {
    for (const [square, type, color] of requiredPieces[right] || []) {
      const piece = board.get(square);
      assert(
        piece?.type === type && piece?.color === color,
        `${lessonId} has impossible ${right} castling rights`
      );
    }
  }
}

assert(TRAINING_LESSONS.length >= 16, `expected at least 16 lessons, got ${TRAINING_LESSONS.length}`);

for (const lesson of TRAINING_LESSONS) {
  assert(lesson.id && !seenIds.has(lesson.id), `lesson id must be unique: ${lesson.id}`);
  seenIds.add(lesson.id);
  assert(REQUIRED_PHASES.has(lesson.phase), `${lesson.id} has invalid phase ${lesson.phase}`);
  assert(Array.isArray(lesson.tags) && lesson.tags.length >= 2, `${lesson.id} needs at least two tags`);
  assert(ALLOWED_TYPES.has(lesson.type), `${lesson.id} has invalid type ${lesson.type}`);
  assert(Number.isInteger(lesson.difficulty) && lesson.difficulty >= 1 && lesson.difficulty <= 3, `${lesson.id} has invalid difficulty`);
  assert(ALLOWED_SIDES.has(lesson.side), `${lesson.id} has invalid side ${lesson.side}`);
  assert(Array.isArray(lesson.prerequisites), `${lesson.id} needs prerequisites`);
  assert(lesson.opening && lesson.variation && lesson.goal, `${lesson.id} is missing display copy`);
  assert(Array.isArray(lesson.moves) && lesson.moves.length >= 1, `${lesson.id} needs moves`);
  assert(Array.isArray(lesson.ideas) && lesson.ideas.length >= 2, `${lesson.id} needs learning ideas`);

  const board = lesson.startFen ? new Chess(lesson.startFen) : new Chess();
  validatePositionSemantics(board, lesson.id, lesson.startFen || board.fen());
  assert(lesson.recommendationVerified, `${lesson.id} changed since its accuracy verification`);
  for (const san of lesson.moves) {
    const move = board.move(san);
    assert(move, `${lesson.id} has illegal SAN ${san} from ${board.fen()}`);
  }

  phaseCounts.set(lesson.phase, (phaseCounts.get(lesson.phase) || 0) + 1);
}

for (const lesson of TRAINING_LESSONS) {
  for (const prerequisite of lesson.prerequisites) {
    assert(seenIds.has(prerequisite), `${lesson.id} has missing prerequisite ${prerequisite}`);
    assert(prerequisite !== lesson.id, `${lesson.id} cannot require itself`);
  }
}

for (const phase of REQUIRED_PHASES) {
  assert((phaseCounts.get(phase) || 0) >= 4, `${phase} should have at least 4 lessons`);
}

console.log(`Validated ${TRAINING_LESSONS.length} training lessons.`);
