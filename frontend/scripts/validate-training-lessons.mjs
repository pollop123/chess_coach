import { Chess } from "chess.js";
import { TRAINING_LESSONS } from "../src/trainingLessons.js";

const REQUIRED_PHASES = new Set(["opening", "middlegame", "endgame"]);
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

for (const phase of REQUIRED_PHASES) {
  assert((phaseCounts.get(phase) || 0) >= 4, `${phase} should have at least 4 lessons`);
}

console.log(`Validated ${TRAINING_LESSONS.length} training lessons.`);
