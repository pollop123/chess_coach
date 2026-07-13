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
