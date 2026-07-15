import unittest

import chess

import validate_training_lessons


class TrainingLessonValidatorTests(unittest.TestCase):
    def test_current_catalog_has_semantically_valid_positions_and_moves(self):
        lessons = validate_training_lessons.load_lessons()
        self.assertEqual(validate_training_lessons.validate_semantics(lessons), [])

    def test_rejects_position_where_non_moving_side_is_in_check(self):
        lessons = [{
            "id": "invalid-opposite-check",
            "startFen": "7k/6Q1/5K2/8/8/8/8/8 w - - 0 1",
            "moves": ["Kf7#"],
        }]
        errors = validate_training_lessons.validate_semantics(lessons)
        self.assertEqual(len(errors), 1)
        self.assertIn(str(int(chess.STATUS_OPPOSITE_CHECK)), errors[0])

    def test_rejects_illegal_later_move(self):
        lessons = [{"id": "bad-line", "moves": ["e4", "e5", "Qh5", "Nc6", "Qh8"]}]
        errors = validate_training_lessons.validate_semantics(lessons)
        self.assertEqual(len(errors), 1)
        self.assertIn("illegal SAN at ply 5", errors[0])

    def test_accuracy_thresholds_reject_loose_puzzle_and_guided_moves(self):
        puzzle = {"type": "puzzle", "tags": ["tactics"]}
        guided = {"type": "guided", "tags": ["center"]}
        self.assertFalse(validate_training_lessons.first_move_is_acceptable(
            puzzle, loss_cp=31, preserves_outcome=True, delivers_checkmate=False
        ))
        self.assertFalse(validate_training_lessons.first_move_is_acceptable(
            guided, loss_cp=81, preserves_outcome=True, delivers_checkmate=False
        ))

    def test_checkmate_lesson_requires_the_lesson_move_to_mate(self):
        lesson = {"type": "puzzle", "tags": ["checkmate"]}
        self.assertFalse(validate_training_lessons.first_move_is_acceptable(
            lesson, loss_cp=0, preserves_outcome=True, delivers_checkmate=False
        ))
        self.assertTrue(validate_training_lessons.first_move_is_acceptable(
            lesson, loss_cp=0, preserves_outcome=True, delivers_checkmate=True
        ))

    def test_explicit_guided_exception_is_narrow_and_still_preserves_outcome(self):
        lesson = {"type": "guided", "tags": ["promotion"], "engineMaxCpLoss": 250}
        self.assertTrue(validate_training_lessons.first_move_is_acceptable(
            lesson, loss_cp=200, preserves_outcome=True, delivers_checkmate=False
        ))
        self.assertFalse(validate_training_lessons.first_move_is_acceptable(
            lesson, loss_cp=200, preserves_outcome=False, delivers_checkmate=False
        ))


if __name__ == "__main__":
    unittest.main()
