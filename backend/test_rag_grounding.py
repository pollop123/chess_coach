import unittest

import chess
from unittest.mock import patch

from openings import identify_opening, load_opening_index
from rag import ChessRAG, build_move_facts, strip_unverified_opening_claims


class RagGroundingTests(unittest.TestCase):
    def test_opening_identification_uses_longest_verified_line(self):
        cases = {
            "1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5": "Italian Game: Giuoco Piano",
            "1. e4 e5 2. Nf3 Nc6 3. Bc4 Nf6": "Italian Game: Two Knights Defense",
            "1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 4. b4": "Italian Game: Evans Gambit",
            "1. e4 c5 2. Nf3 d6 3. d4 cxd4 4. Nxd4 Nf6 5. Nc3 a6": "Sicilian Defense: Najdorf Variation",
        }

        for pgn, expected in cases.items():
            with self.subTest(pgn=pgn):
                self.assertEqual(identify_opening(pgn)["official_name"], expected)

    def test_complete_eco_dataset_is_loaded(self):
        index = load_opening_index()

        self.assertGreaterEqual(len(index), 3000)
        self.assertEqual({record.eco[0] for record in index.values()}, set("ABCDE"))

    def test_unknown_opening_is_not_named(self):
        self.assertIsNone(identify_opening(""))

    def test_identification_walks_back_after_the_book_line_ends(self):
        result = identify_opening(
            "1. e4 c5 2. Nf3 d6 3. d4 cxd4 4. Nxd4 Nf6 "
            "5. Nc3 a6 6. Nb1 h6 7. a3"
        )

        self.assertEqual(result["eco"], "B90")
        self.assertEqual(result["official_name"], "Sicilian Defense: Najdorf Variation")
        self.assertEqual(result["matched_plies"], 10)

    def test_identification_handles_transposed_move_order(self):
        standard = identify_opening("1. d4 d5 2. Nf3 Nf6 3. Bf4")
        transposed = identify_opening("1. Nf3 Nf6 2. d4 d5 3. Bf4")

        self.assertEqual(transposed["eco"], "D02")
        self.assertEqual(transposed["official_name"], standard["official_name"])
        self.assertIn("后兵開局", transposed["name"])

    def test_move_facts_are_derived_from_board(self):
        board = chess.Board(
            "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4"
        )
        facts = build_move_facts(board, chess.Move.from_uci("h5f7"))

        self.assertIn("SAN：Qxf7#", facts)
        self.assertIn("移動棋子：后", facts)
        self.assertIn("吃子：兵", facts)
        self.assertIn("將死：是", facts)
        self.assertIn("目的格支援子：象@c4", facts)

    def test_advice_uses_verified_opening_and_move_facts(self):
        rag = ChessRAG()
        rag.client = object()
        rag.retrieve_rule = lambda _query: "開局原則"
        rag.retrieve_similar_game = lambda _fen: "無相似歷史對局。"

        generated_prompts = []

        def fake_generate(prompt, _system_instruction=None):
            generated_prompts.append(prompt)
            return "這是不應被信任的 Légal Trap 說法。"

        rag.call_gemini_with_fallback = fake_generate
        analysis = {
            "best_move": chess.Move.from_uci("h5f7"),
            "from_book": False,
            "book_line": [],
        }

        with patch("rag.chess_engine.get_analysis", return_value=analysis):
            advice = rag.get_advice(
                "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4",
                "1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6",
                "這是什麼開局？",
                analysis_result=analysis,
            )

        self.assertTrue(advice.startswith("開局辨識：C23 象開局（Bishop's Opening"))
        self.assertIn("移動棋子：后", generated_prompts[0])
        self.assertIn("將死：是", generated_prompts[0])
        self.assertIn("目的格支援子：象@c4", generated_prompts[0])
        self.assertNotIn("Légal Trap", advice)

    def test_advice_prompt_includes_verified_teaching_analysis(self):
        rag = ChessRAG()
        rag.client = object()
        rag.retrieve_rule = lambda _query: "開局原則"
        rag.retrieve_similar_game = lambda _fen: "無相似歷史對局。"

        generated_prompts = []

        def fake_generate(prompt, _system_instruction=None):
            generated_prompts.append(prompt)
            return "Nf3 發展子力。"

        rag.call_gemini_with_fallback = fake_generate
        analysis = {
            "best_move": chess.Move.from_uci("g1f3"),
            "from_book": False,
            "book_line": [],
        }
        teaching_analysis = {
            "criticality": "sharp",
            "best_move_reason": "develops_piece",
            "position_themes": ["opening_principle", "development"],
            "mistake_warnings": ["large_eval_drop"],
            "candidates": [
                {
                    "rank": 1,
                    "san": "Nf3",
                    "score_cp": 35,
                    "loss_cp": 0,
                    "warnings": [],
                    "themes": ["development"],
                    "pv": ["g1f3", "b8c6"],
                    "reason": "develops_piece",
                },
                {
                    "rank": 2,
                    "san": "Qh5",
                    "score_cp": -120,
                    "loss_cp": 155,
                    "warnings": ["large_eval_drop"],
                    "themes": ["tactics"],
                    "pv": ["d1h5"],
                    "reason": "best_engine_score",
                },
            ],
        }

        rag.get_advice(
            chess.STARTING_FEN,
            "",
            "怎麼下比較好？",
            analysis_result=analysis,
            teaching_analysis=teaching_analysis,
        )

        prompt = generated_prompts[0]
        self.assertIn("[已驗證教學分析]", prompt)
        self.assertIn("criticality=sharp", prompt)
        self.assertIn("best_move_reason=develops_piece", prompt)
        self.assertIn("#1 Nf3 score=35 loss=0", prompt)
        self.assertIn("warnings=large_eval_drop", prompt)
        self.assertIn("themes=opening_principle, development", prompt)

    def test_unverified_opening_names_are_removed_from_generated_text(self):
        advice = "這是 Légal Trap。\n白后與白象正在同時攻擊 f7。"

        self.assertEqual(
            strip_unverified_opening_claims(advice),
            "白后與白象正在同時攻擊 f7。",
        )


if __name__ == "__main__":
    unittest.main()
