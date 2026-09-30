import os
from google import genai
from google.genai import types
import chess
import chess.pgn
import io
import json
import logging
import re
import time
import chess_engine
from openings import identify_opening
from coach_evidence import (
    EvidenceSource, KNOWLEDGE_SOURCES, rank_knowledge, render_sources,
)
from coach_facts import LAST_MOVE_QUESTION, last_move_source, move_fact_summary, threat_source
from coach_conversation import current_conversation, question_mode, retrieval_question, wants_brief_answer
from coach_generation import (
    CoachReply, NATURAL_INSTRUCTION, NATURAL_SCHEMA, VERIFY_INSTRUCTION,
    VERIFY_SCHEMA, chess_atoms, hint_sources, natural_schema, parse_natural_answer,
    render_natural_answer, review_passed,
)

logger = logging.getLogger(__name__)

# One reviewed corpus is shared by lexical and optional vector retrieval.
KNOWLEDGE_DOCUMENTS = [source.text for source in KNOWLEDGE_SOURCES]

PIECE_NAMES = {
    chess.PAWN: "兵",
    chess.KNIGHT: "馬",
    chess.BISHOP: "象",
    chess.ROOK: "車",
    chess.QUEEN: "后",
    chess.KING: "王",
}


def build_move_facts(board, move):
    if board is None or not isinstance(move, chess.Move) or move not in board.legal_moves:
        return "無可驗證的推薦手事實。"

    moving_piece = board.piece_at(move.from_square)
    captured_piece = None
    if board.is_en_passant(move):
        captured_square = move.to_square - 8 if board.turn == chess.WHITE else move.to_square + 8
        captured_piece = board.piece_at(captured_square)
    elif board.is_capture(move):
        captured_piece = board.piece_at(move.to_square)

    san = board.san(move)
    mover_color = board.turn
    after = board.copy()
    after.push(move)

    facts = [
        f"合法走法：是",
        f"SAN：{san}",
        f"移動棋子：{PIECE_NAMES.get(moving_piece.piece_type, '未知棋子') if moving_piece else '未知棋子'}",
        f"路徑：{chess.square_name(move.from_square)} 到 {chess.square_name(move.to_square)}",
        f"吃子：{PIECE_NAMES.get(captured_piece.piece_type, '未知棋子') if captured_piece else '否'}",
        f"將軍：{'是' if after.is_check() else '否'}",
        f"將死：{'是' if after.is_checkmate() else '否'}",
    ]

    defenders = []
    for square in after.attackers(mover_color, move.to_square):
        piece = after.piece_at(square)
        if piece:
            defenders.append(f"{PIECE_NAMES.get(piece.piece_type, '棋子')}@{chess.square_name(square)}")
    facts.append(f"目的格支援子：{', '.join(defenders) if defenders else '無'}")
    return "；".join(facts)


def strip_unverified_opening_claims(advice):
    if not advice:
        return advice

    naming_terms = re.compile(
        r"(開局|防禦|棄兵|陷阱|\bopening\b|\bdefen[cs]e\b|\bgambit\b|\btrap\b)",
        re.IGNORECASE,
    )
    kept_lines = [line for line in advice.splitlines() if not naming_terms.search(line)]
    cleaned = "\n".join(kept_lines).strip()
    return cleaned or "請以上方已驗證的開局辨識為準。"


def format_teaching_analysis(teaching_analysis):
    if not teaching_analysis:
        return "無。"

    complete = bool(teaching_analysis.get("analysis_complete"))
    lines = [
        "[結構化教學分析]",
        f"analysis_complete={'true' if complete else 'false'}",
        f"candidate_count={teaching_analysis.get('evaluated_candidate_count', 0)}/"
        f"{teaching_analysis.get('requested_candidate_count', 0)}",
        f"criticality={teaching_analysis.get('criticality', 'normal')}",
        f"best_move_reason={teaching_analysis.get('best_move_reason', 'best_engine_score')}",
        f"best_move_evidence={teaching_analysis.get('best_move_evidence', 'heuristic')}",
    ]
    if teaching_analysis.get("displayed_move"):
        lines.append(f"displayed_move={teaching_analysis['displayed_move']}")
        lines.append(
            f"displayed_candidate_rank={teaching_analysis.get('displayed_candidate_rank', 'unknown')}"
        )

    themes = teaching_analysis.get("position_themes") or []
    if themes:
        lines.append(f"themes={', '.join(themes)}")
        theme_evidence = teaching_analysis.get("position_theme_evidence") or {}
        lines.append(
            "theme_evidence="
            + ", ".join(
                f"{theme}:{theme_evidence.get(theme, 'heuristic')}"
                for theme in themes
            )
        )
    candidate_themes = teaching_analysis.get("candidate_themes") or []
    if candidate_themes:
        lines.append(f"all_candidate_themes={', '.join(candidate_themes)}")

    mistake_warnings = teaching_analysis.get("mistake_warnings") or []
    if mistake_warnings:
        lines.append(f"mistake_warnings={', '.join(mistake_warnings)}")

    candidates = teaching_analysis.get("candidates") or []
    if candidates:
        lines.append("候選手比較:")
    for item in candidates[:6]:
        warnings = ", ".join(item.get("warnings") or []) or "none"
        item_themes = ", ".join(item.get("themes") or []) or "none"
        item_theme_evidence = item.get("theme_evidence") or {}
        item_theme_evidence_text = ", ".join(
            f"{theme}:{item_theme_evidence.get(theme, 'heuristic')}"
            for theme in (item.get("themes") or [])
        ) or "none"
        pv = " ".join(item.get("pv") or []) or "none"
        lines.append(
            f"#{item.get('rank')} {item.get('san')} "
            f"score={item.get('score_cp')} loss={item.get('loss_cp')} "
            f"score_type={item.get('score_type', 'centipawn')} "
            f"score_status={item.get('score_status', 'unknown')} "
            f"reason={item.get('reason')} evidence={item.get('reason_evidence', 'heuristic')} warnings={warnings} "
            f"themes={item_themes} theme_evidence={item_theme_evidence_text} pv={pv}"
        )

    return "\n".join(lines)


def align_teaching_analysis(teaching_analysis, displayed_move=None):
    """Bind top-level teaching claims to the move shown to the player."""
    if not teaching_analysis:
        return teaching_analysis

    candidates = teaching_analysis.get("candidates") or []
    selected = None
    if displayed_move:
        selected = next(
            (
                item for item in candidates
                if displayed_move in {item.get("san"), item.get("move")}
            ),
            None,
        )
    if selected is None:
        selected = next(
            (item for item in candidates if item.get("base_engine_choice")),
            None,
        )
    if selected is None:
        return dict(teaching_analysis)

    aligned = dict(teaching_analysis)
    reason = selected.get("reason")
    if reason:
        aligned["best_move_reason"] = reason
        aligned["best_move_evidence"] = (
            selected.get("reason_evidence") or chess_engine._reason_evidence(reason)
        )

    selected_themes = list(
        selected.get("themes")
        if "themes" in selected
        else teaching_analysis.get("position_themes") or []
    )
    if teaching_analysis.get("criticality") == "only_move" and "only_move" not in selected_themes:
        selected_themes.append("only_move")
    aligned["position_themes"] = sorted(selected_themes)
    selected_theme_evidence = dict(
        selected.get("theme_evidence")
        if "theme_evidence" in selected
        else teaching_analysis.get("position_theme_evidence") or {}
    )
    for theme in selected_themes:
        selected_theme_evidence.setdefault(theme, chess_engine._theme_evidence(theme, reason))
    aligned["position_theme_evidence"] = selected_theme_evidence
    aligned["displayed_move"] = selected.get("san") or displayed_move
    aligned["displayed_candidate_rank"] = selected.get("rank")
    return aligned


def build_retrieval_query(user_question, board=None, teaching_analysis=None):
    """Combine the player's wording with verified position signals."""
    parts = [(user_question or "").strip()]
    if board is not None:
        phase = chess_engine.detect_game_phase(board)
        phase_labels = {
            "opening": "開局 發展 中心 王安全",
            "middle_game": "中局 戰術 計算 攻王",
            "endgame": "殘局 王 通路兵 升變",
        }
        parts.append(phase_labels.get(phase, phase))

    teaching_analysis = teaching_analysis or {}
    themes = teaching_analysis.get("position_themes") or []
    warnings = teaching_analysis.get("mistake_warnings") or []
    reason = teaching_analysis.get("best_move_reason")
    parts.extend(str(item) for item in [*themes, *warnings, reason] if item)
    return " ".join(part for part in parts if part).strip() or "General chess strategy"


ADVICE_SECTION_LABELS = (
    "局面判斷",
    "推薦手",
    "選這步的原因",
    "對手最強回應",
    "應避免",
    "一句話心法",
)


def _parse_advice_sections(advice):
    sections = {}
    current = None
    for raw_line in (advice or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        matched = False
        for label in ADVICE_SECTION_LABELS:
            prefix = f"{label}："
            if line.startswith(prefix):
                current = label
                sections[label] = line[len(prefix):].strip()
                matched = True
                break
        if not matched and current:
            sections[current] = f"{sections[current]} {line}".strip()
    return sections


def _reason_text(teaching_analysis):
    teaching_analysis = teaching_analysis or {}
    if teaching_analysis.get("analysis_complete") is False:
        return "候選手比較尚未完成；目前只能沿用基礎引擎選擇，不能宣稱已完整比較。"
    if teaching_analysis.get("analysis_complete") is not True:
        return "尚未取得完整候選手分析，目前沒有足夠證據解釋這個推薦。"
    reason = teaching_analysis.get("best_move_reason")
    labels = {
        "checkmate": "這步會直接將死。",
        "check": "這步會直接將軍。",
        "wins_material": "合理的一手吃回後，這步仍保有可見的物質收益。",
        "avoids_major_piece_loss": "盤面顯示該后或車原先受攻擊，走後直接攻擊已解除。",
        "creates_valuable_piece_fork": "走後同一枚棋子會同時直接攻擊至少兩枚非兵子。",
        "develops_piece": "這步把尚未發展的子力帶入戰局。",
        "controls_center": "走後的棋子會控制至少一個核心中心格。",
        "improves_king_safety": "走後己方王區受到的直接攻擊減少。",
        "attacks_enemy_king": "走後對方王區受到的直接壓力增加。",
        "resolves_check": "這步合法解除目前的將軍。",
        "castle": "這步完成王車易位。",
        "promotes_or_supports_promotion": "這步完成合法升變。",
        "best_engine_score": "這步由基礎引擎選出。",
    }
    fact = labels.get(reason, "目前只有一般棋理線索支持這步。")
    if reason == "best_engine_score":
        rank = teaching_analysis.get("displayed_candidate_rank")
        if isinstance(rank, int) and rank > 1:
            fact = f"這步由基礎引擎選出；在教學候選手重評中排名第 {rank}，兩輪搜尋結果並不完全一致。"
    evidence = teaching_analysis.get("best_move_evidence") or chess_engine._reason_evidence(reason)
    if evidence == "verified":
        return f"盤面可直接確認：{fact}"
    if evidence == "supported":
        return f"引擎評分與盤面特徵支持：{fact}"
    return f"依一般棋理，這步可能有助於：{fact}"


def _summary_text(teaching_analysis):
    teaching_analysis = teaching_analysis or {}
    if teaching_analysis.get("analysis_complete") is False:
        return "候選手分析尚未完成，目前只宜把引擎推薦視為暫時方向。"
    if teaching_analysis.get("analysis_complete") is not True:
        return "目前沒有完整的候選手與盤面證據，無法形成可驗證的局面判斷。"
    reason = teaching_analysis.get("best_move_reason")
    themes = set(teaching_analysis.get("position_themes") or [])
    theme_evidence = teaching_analysis.get("position_theme_evidence") or {}

    if reason == "checkmate" and teaching_analysis.get("best_move_evidence") == "verified":
        return "局面存在已驗證的直接將殺，應優先計算所有強制將軍。"
    if "endgame" in themes:
        if theme_evidence.get("endgame") == "supported":
            return "盤面特徵支持以殘局方式思考，可檢查王的參戰與通路兵計畫。"
        return "依一般棋理，這個局面可能需要殘局式的王與通路兵規劃。"
    if "center_control" in themes or "opening_principle" in themes:
        return "依一般棋理，這個局面可能適合檢查中心控制、子力發展與王的安全。"
    if "king_safety" in themes:
        if theme_evidence.get("king_safety") == "supported":
            return "盤面特徵支持先檢查雙方王的安全與強制手。"
        return "依一般棋理，可能需要先檢查雙方王的安全。"
    if "tactics" in themes:
        evidence = theme_evidence.get("tactics", "heuristic")
        if evidence == "verified":
            return "盤面可直接確認強制戰術，應先依序檢查將軍、吃子與直接威脅。"
        if evidence == "supported":
            return "引擎評分與盤面特徵支持這是戰術性局面，可先檢查強制手。"
        return "依一般棋理，這個局面可能具有戰術性，可先檢查強制手。"
    return "候選手比較已完成，但目前沒有足夠的盤面證據支持更具體的主題判斷。"


def _principle_text(teaching_analysis):
    teaching_analysis = teaching_analysis or {}
    if teaching_analysis.get("analysis_complete") is False:
        return "分析未完成時先保留判斷，重新取得完整候選手比較後再下結論。"
    if teaching_analysis.get("analysis_complete") is not True:
        return "資料不足時先確認合法手、將軍與吃子，不強行診斷局面主題。"
    reason = teaching_analysis.get("best_move_reason")
    themes = set(teaching_analysis.get("position_themes") or [])

    if reason == "checkmate" or "mate" in themes:
        return "看到王附近有強制手時，先依序檢查將軍、吃子與直接威脅。"
    if reason == "creates_valuable_piece_fork":
        return "發現一子同時攻擊兩個高價值目標時，先檢查對手能否一次化解全部威脅。"
    if "rook_endgame" in themes:
        return "車殘局先讓車保持活躍，再檢查王的位置、通路兵與對手的側後方將軍。"
    if "queen_endgame" in themes:
        return "后殘局先檢查連續將軍、王的安全與換后後的兵殘局結果。"
    if "minor_piece_endgame" in themes:
        return "小子殘局先改善王與小子的活動力，再判斷兵型與通路兵。"
    if "pawn_endgame" in themes or reason == "promotes_or_supports_promotion":
        return "兵殘局先讓王靠近關鍵格，再決定推兵與升變的時機。"
    if "endgame" in themes or reason == "improves_king_safety":
        return "殘局先檢查王的活躍度、兵的結構、交換後結果與對手反擊。"
    if reason == "controls_center" or "center_control" in themes:
        return "先控制中心，再用子力發展把空間優勢轉成主動權。"
    if reason == "develops_piece" or "development" in themes:
        return "優先把未發展的子力帶入戰局，再考慮重複走子或提早進攻。"
    if reason in {"wins_material", "avoids_major_piece_loss"}:
        return "比較候選手時，同時檢查己方懸掛棋子與對手最強反擊。"
    return "先比較候選手，再用對手最強回應檢查自己的想法。"


def _avoid_text(teaching_analysis, displayed_move=None):
    if (teaching_analysis or {}).get("analysis_complete") is False:
        return "候選手比較尚未完成，暫不對特定走法的掉分或警告下結論。"
    warning_labels = {
        "large_eval_drop": "評估大幅下降",
        "hangs_major_piece": "可能送掉后或車",
        "misses_mate": "錯失將殺",
        "allows_mate_threat": "允許對手形成將殺威脅",
    }
    ranked = []
    warning_priority = {
        "misses_mate": 4,
        "allows_mate_threat": 3,
        "hangs_major_piece": 2,
        "large_eval_drop": 1,
    }
    for item in (teaching_analysis or {}).get("candidates") or []:
        if displayed_move and displayed_move in {item.get("san"), item.get("move")}:
            continue
        warnings = item.get("warnings") or []
        loss = int(item.get("loss_cp") or 0)
        if warnings or loss >= 100:
            priority = max((warning_priority.get(warning, 0) for warning in warnings), default=0)
            ranked.append((priority, loss, item))
    if ranked:
        _priority, loss, item = max(ranked, key=lambda entry: (entry[0], entry[1]))
        warnings = item.get("warnings") or []
        warning_text = "、".join(warning_labels.get(warning, warning) for warning in warnings)
        if not warning_text:
            warning_text = f"約損失 {loss}cp"
        return f"{item.get('san')}（{warning_text}）"
    return "避免只看單一步威脅；走棋前先檢查將軍、吃子與對手反擊。"


def format_grounded_advice(_generated_advice, engine_best_move, teaching_analysis=None, verified_reply=None,
                           move_fact=None):
    """Build the stable advice contract entirely from verified move fields."""
    # Keep the first argument for compatibility with existing callers. Model
    # prose is deliberately ignored because none of its claims are verified.
    aligned_teaching = align_teaching_analysis(teaching_analysis, engine_best_move)
    summary = _summary_text(aligned_teaching)
    reason = _reason_text(aligned_teaching)
    if move_fact and (aligned_teaching or {}).get("analysis_complete") is not True:
        # A mate or capture is certain from the board even when the slower
        # candidate comparison did not finish.
        reason = f"盤面可直接確認：{move_fact}"
    reply = verified_reply or "目前沒有已驗證的後續回應。"
    avoid = _avoid_text(aligned_teaching, engine_best_move)
    principle = _principle_text(aligned_teaching)

    return "\n".join([
        f"局面判斷：{summary}",
        f"推薦手：{engine_best_move or '目前沒有可驗證的推薦手'}",
        f"選這步的原因：{reason}",
        f"對手最強回應：{reply}",
        f"應避免：{avoid}",
        f"一句話心法：{principle}",
    ])


def _simple_retrieve_rule(search_query):
    return render_sources(rank_knowledge(search_query)[:4])


def _history_at_position(history, board):
    """Only identify openings from the PGN prefix reaching the displayed board."""
    if not history:
        return ""
    try:
        game = chess.pgn.read_game(io.StringIO(history))
        if not game or game.errors:
            return ""
        replay = game.board()
        target = " ".join(board.fen().split()[:4])
        if " ".join(replay.fen().split()[:4]) == target:
            return ""
        prefix = chess.pgn.Game.from_board(replay)
        node = prefix
        for move in game.mainline_moves():
            node = node.add_variation(move)
            replay.push(move)
            if " ".join(replay.fen().split()[:4]) == target:
                return prefix.accept(chess.pgn.StringExporter(headers=True, variations=False, comments=False))
    except (ValueError, TypeError):
        pass
    return ""


def _verified_reply(board, best_move, analysis_result, pv_line):
    """A legal PV must start with the displayed move before its reply is used."""
    if not best_move:
        return None
    replay = board.copy()
    try:
        if analysis_result.get("from_book"):
            line = analysis_result.get("book_line") or []
            if len(line) < 2:
                return None
            first = replay.parse_san(line[0])
            if first != best_move:
                return None
            replay.push(first)
            return replay.san(replay.parse_san(line[1]))
        if not pv_line or len(pv_line) < 2:
            return None
        first = chess.Move.from_uci(pv_line[0])
        if first != best_move or first not in replay.legal_moves:
            return None
        replay.push(first)
        reply = chess.Move.from_uci(pv_line[1])
        return replay.san(reply) if reply in replay.legal_moves else None
    except (ValueError, TypeError):
        return None


def _candidate_sources(board, teaching_analysis):
    teaching = teaching_analysis or {}
    sources = []
    for index, candidate in enumerate(teaching.get("candidates") or [], start=1):
        if index > 6:
            break
        try:
            move = board.parse_uci(candidate.get("move", ""))
        except (ValueError, TypeError):
            continue
        if move not in board.legal_moves:
            continue
        san = board.san(move)
        if teaching.get("analysis_complete") is not True or candidate.get("score_status") != "complete":
            text = f"候選手 {san} 尚無完整比較結果，不能據此確認掉分或排名。"
        else:
            loss = candidate.get("loss_cp")
            comparison = (
                f"相對本次候選集合最高評分約損失 {loss}cp"
                if type(loss) is int and loss >= 0
                else "目前分數涉及將殺或資料不足，不能用一般百分兵掉分比較"
            )
            text = f"候選手 {san}：{comparison}。" + _reason_text(align_teaching_analysis(teaching, san))
        sources.append(EvidenceSource(f"C{index}", f"候選手 {san} 比較", text, "position"))
    return sources


class ChessRAG:
    def __init__(self):
        self.chroma_client = None
        self.rule_collection = None
        self.game_collection = None
        self.client = None

        # Prefer lightweight text models that are available in Gemini API.
        self.backup_models = [
            "gemini-3.1-flash-lite",
            "gemini-2.5-flash",
        ]

        api_key = os.getenv("GOOGLE_API_KEY")
        if api_key:
            try:
                self.client = genai.Client(
                    api_key=api_key,
                    http_options=types.HttpOptions(
                        timeout=12000,
                        retry_options=types.HttpRetryOptions(attempts=1),
                    ),
                )
            except Exception as exc:
                logger.warning("Coach client unavailable (%s)", type(exc).__name__)

        if os.getenv("ENABLE_CHROMA_RAG", "").lower() in {"1", "true", "yes"}:
            try:
                import chromadb

                self.chroma_client = chromadb.PersistentClient(path="./chroma_db")
                self.rule_collection = self.chroma_client.get_or_create_collection(name="chess_knowledge")
                self.game_collection = self.chroma_client.get_or_create_collection(name="chess_games")

                self.add_knowledge()
                if self.game_collection.count() == 0:
                    self.seed_master_games()
            except Exception as exc:
                logger.warning("Chroma RAG unavailable (%s)", type(exc).__name__)
                self.chroma_client = None
                self.rule_collection = None
                self.game_collection = None

    def add_knowledge(self):
        """Refresh the reviewed corpus, including existing nonempty collections."""
        self.rule_collection.upsert(
            documents=KNOWLEDGE_DOCUMENTS,
            ids=[f"rule_{index}" for index in range(len(KNOWLEDGE_SOURCES))],
            metadatas=[{"source_id": source.id, "title": source.title} for source in KNOWLEDGE_SOURCES],
        )

    def seed_master_games(self):
        # 簡化版種子
        print("🌱 初始化種子棋譜...")
        sample_pgn = """
        [Event "The Immortal Game"]
        [Site "London"]
        [White "Adolf Anderssen"]
        [Black "Lionel Kieseritzky"]
        [Result "1-0"]
        1. e4 e5 2. f4 exf4 3. Bc4 Qh4+ 4. Kf1 b5 5. Bxb5 Nf6 6. Nf3 Qh6 7. d3 Nh5 8. Nh4 Qg5 9. Nf5 c6 10. g4 Nf6 11. Rg1 cxb5 12. h4 Qg6 13. h5 Qg5 14. Qf3 Ng8 15. Bxf4 Qf6 16. Nc3 Bc5 17. Nd5 Qxb2 18. Bd6 Bxg1 19. e5 Qxa1+ 20. Ke2 Na6 21. Nxg7+ Kd8 22. Qf6+ Nxf6 23. Be7# 1-0
        """
        pgn = io.StringIO(sample_pgn)
        game = chess.pgn.read_game(pgn)
        board = game.board()
        docs, ids, metas = [], [], []
        for i, move in enumerate(game.mainline_moves()):
            board.push(move)
            docs.append(board.fen())
            ids.append(f"immortal_{i}")
            metas.append({"white": "Anderssen", "black": "Kieseritzky", "result": "1-0", "last_move": move.uci(), "source": "master"})
        self.game_collection.add(documents=docs, ids=ids, metadatas=metas)

    def call_gemini_with_fallback(self, prompt, system_instruction=NATURAL_INSTRUCTION,
                                  response_schema=None, deadline=None):
        if not self.client:
            return None
        # The provider rejects deadlines below ten seconds. Both models share
        # a budget; do not start a fallback when it cannot meet that minimum.
        minimum_timeout = 10.0
        budget = min(30.0, max(minimum_timeout, float(os.getenv("RAG_TIMEOUT_SECONDS", "20"))))
        shared_deadline = deadline is not None
        deadline = deadline if shared_deadline else time.monotonic() + budget
        for index, model in enumerate(self.backup_models):
            remaining = budget if index == 0 and not shared_deadline else deadline - time.monotonic()
            if remaining < minimum_timeout:
                break
            try:
                response = self.client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0,
                        max_output_tokens=2048,
                        response_mime_type="application/json",
                        response_json_schema=response_schema or NATURAL_SCHEMA,
                        http_options=types.HttpOptions(
                            timeout=int(remaining * 1000),
                            retry_options=types.HttpRetryOptions(attempts=1),
                        ),
                    ),
                )
                if response.text:
                    return response.text
            except Exception as exc:
                # Do not log prompts, credentials, or provider response bodies.
                logger.warning(
                    "Coach model %s failed (%s, status=%s)",
                    model, type(exc).__name__, getattr(exc, "code", None),
                )
        return None

    def retrieve_rule_sources(self, search_query, user_question=""):
        lexical = rank_knowledge(search_query, user_question)
        vector = []
        if self.rule_collection is not None:
            try:
                count = self.rule_collection.count()
                if count:
                    results = self.rule_collection.query(
                        query_texts=[search_query], n_results=min(6, count),
                    )
                    known_text = {source.text: source for source in KNOWLEDGE_SOURCES}
                    for document in (results.get("documents") or [[]])[0]:
                        # Stored vectors rank sources; the reviewed local corpus
                        # supplies the text. Arbitrary DB text is never evidence.
                        source = known_text.get(document)
                        if source is not None and source not in vector:
                            vector.append(source)
            except Exception as exc:
                logger.warning("Coach retrieval fallback (%s)", type(exc).__name__)
        # Explicit question matches lead; semantic hits can add relevant context.
        explicit = rank_knowledge(user_question, user_question)
        merged = []
        for source in [*explicit[:2], *vector, *lexical]:
            if source not in merged:
                merged.append(source)
        return merged[:4]

    def retrieve_rule(self, search_query):
        return render_sources(self.retrieve_rule_sources(search_query))

    def retrieve_similar_game(self, fen):
        if not self.game_collection:
            return "輕量知識庫模式：目前不查詢相似歷史對局。"

        try:
            game_results = self.game_collection.query(query_texts=[fen], n_results=1)
        except Exception as e:
            print(f"Chroma game retrieval failed: {e}")
            return "輕量知識庫模式：目前不查詢相似歷史對局。"

        if not (game_results["documents"] and game_results["documents"][0]):
            return "無相似歷史對局。"

        dist = game_results["distances"][0][0]
        meta = game_results["metadatas"][0][0]
        if dist >= 0.6:
            return "無相似歷史對局。"

        white = meta.get("white", "?")
        black = meta.get("black", "?")
        move = meta.get("last_move", "?")
        source = meta.get("source", "master")

        if "lichess" in source:
            return f"[Lichess 相似局] {white} vs {black}, 高手走了 {move}"
        return f"[歷史名局] {white} vs {black}, 大師走了 {move}"

    def get_response(
        self,
        fen,
        move_history,
        user_question,
        pv_line=None,
        pv_score=None,
        analysis_result=None,
        teaching_analysis=None,
        conversation=None,
        mode="auto",
        review_evidence=None,
        player_color=None,
    ):
        board = chess.Board(fen)
        if not board.is_valid():
            raise ValueError("Invalid board position")
        turns = current_conversation(conversation, fen)
        mode = question_mode(user_question, turns, mode)
        if board.is_game_over() and mode != "knowledge":
            return CoachReply(f"遊戲已結束：{board.result()}。目前沒有可走的推薦手。", mode=mode)

        # Engine analysis stays usable without an external model or API key.
        if analysis_result is None and mode != "knowledge":
            analysis_result = chess_engine.EngineSession().analyze(board, depth=3, time_limit=1.0)
        analysis_result = analysis_result or {}
        best_move = analysis_result.get("best_move")
        if isinstance(best_move, str):
            try:
                best_move = board.parse_uci(best_move)
            except ValueError:
                try:
                    best_move = board.parse_san(best_move)
                except ValueError:
                    best_move = None
        if not isinstance(best_move, chess.Move) or best_move not in board.legal_moves:
            best_move = None
        displayed_move = board.san(best_move) if best_move else None
        teaching_analysis = align_teaching_analysis(teaching_analysis, displayed_move)
        reply = _verified_reply(board, best_move, analysis_result, pv_line or analysis_result.get("pv"))
        move_fact = move_fact_summary(board, best_move) if best_move else None
        grounded_advice = format_grounded_advice(
            "", displayed_move, teaching_analysis=teaching_analysis, verified_reply=reply, move_fact=move_fact,
        )
        opening_result = identify_opening(_history_at_position(move_history, board)) if mode != "knowledge" else None
        opening_header = (
            f"開局辨識：{opening_result['name']}"
            if opening_result
            else "開局辨識：目前棋譜不足以確認，以下不使用未驗證的開局名稱。"
        )

        question = (user_question or "請評估目前局勢並給出建議")[:500]
        search_question = retrieval_question(question, turns)
        query = build_retrieval_query(search_question, board if mode != "knowledge" else None, teaching_analysis)
        rules = self.retrieve_rule_sources(query, search_question)
        # Recheck at the boundary so a failed/custom retriever cannot introduce
        # unreviewed text or impersonate a position fact.
        rules = [source for source in rules if source in KNOWLEDGE_SOURCES][:4]
        sources = list(rules)
        for index, (label, text) in enumerate(_parse_advice_sections(grounded_advice).items(), start=1):
            sources.append(EvidenceSource(f"P{index}", label, text, "position"))
        if best_move:
            sources.append(EvidenceSource("P7", "推薦手盤面事實", build_move_facts(board, best_move), "position"))
        if opening_result:
            sources.append(EvidenceSource("P8", "ECO 棋譜比對", opening_header, "position"))
        sources.extend(_candidate_sources(board, teaching_analysis))
        castles = [board.san(move) for move in board.generate_castling_moves()]
        sources.append(EvidenceSource(
            "P9", "目前易位合法性",
            ("目前走棋方可合法王車易位：" + "、".join(castles) + "。")
            if castles else "目前走棋方沒有合法的王車易位走法。",
            "position",
        ))
        board_facts = []
        if review_evidence is None and mode != "knowledge":
            player = {"white": chess.WHITE, "black": chess.BLACK}.get(player_color)
            board_facts = [source for source in (
                last_move_source(move_history, board, player), threat_source(board),
            ) if source]
            sources.extend(board_facts)

        if review_evidence is not None:
            # Server-owned review evidence replaces the independent teaching
            # search. Preserve only deterministic move/legality/opening facts.
            sources = [*rules, *review_evidence, *[source for source in sources if source.id in {"P7", "P8", "P9"}]]

        if mode == "knowledge":
            sources = rules
        elif mode == "hint":
            sources = hint_sources(board, _principle_text(teaching_analysis))
            sources += [source for source in rules if not chess_atoms(source.text)]
            # Previous answers can contain the solution: hints need only the
            # player's questions, and never the earlier model's concrete moves.
            turns = [turn for turn in turns if turn["role"] == "user"]

        answer = None
        if self.client:
            context = {
                "question": question,
                "conversation": turns,
                "mode": mode,
                "brief": wants_brief_answer(question),
                "engine_recommendation": displayed_move if mode not in {"hint", "knowledge"} else None,
                "sources": [source.as_dict() for source in sources],
            }
            # Generation and semantic review share a single request budget.
            deadline = time.monotonic() + min(30.0, max(20.0, float(os.getenv("RAG_TIMEOUT_SECONDS", "20"))))
            try:
                raw = self.call_gemini_with_fallback(
                    json.dumps(context, ensure_ascii=False),
                    response_schema=natural_schema(sources, context["brief"]), deadline=deadline,
                )
                parsed = parse_natural_answer(raw, sources, mode, brief=context["brief"])
                if parsed is not None:
                    if parsed["insufficient_evidence"]:
                        answer = render_natural_answer(parsed, sources, mode)
                    else:
                        review = self.call_gemini_with_fallback(
                            json.dumps({**context, "answer": parsed}, ensure_ascii=False),
                            system_instruction=VERIFY_INSTRUCTION,
                            response_schema=VERIFY_SCHEMA, deadline=deadline,
                        )
                        if review_passed(review):
                            answer = render_natural_answer(parsed, sources, mode)
            except Exception as exc:
                logger.warning("Coach answer fallback (%s)", type(exc).__name__)
        if answer is None:
            reason = "未啟用語言模型" if not self.client else "問答暫時無法完成或引用未通過核對"
            if mode == "hint":
                advice = sources[0].text
                cited = sources[:1]
            elif mode == "knowledge":
                advice = "\n\n".join(source.text + f" [{source.id}]" for source in rules[:2]) or "目前知識庫沒有足夠資料回答這個問題。"
                cited = rules[:2]
            elif mode == "comparison" and review_evidence is None:
                advice = "目前無法可靠回答這些走法誰更好，不能據此給出確定排名。比較時可先檢查合法性，再計算對手的將軍、吃子與直接威脅。 [K17]"
                cited = [source for source in KNOWLEDGE_SOURCES if source.id == "K17"]
            else:
                if review_evidence is not None:
                    cited = review_evidence
                    advice = "\n\n".join(source.text + f" [{source.id}]" for source in cited)
                    if mode == "comparison":
                        # The review only compared its recommendation with the move played.
                        advice += "\n\n本次分析只比較推薦手與棋譜實際走法；其他走法未經比較，不能據此排名。"
                else:
                    # Exact board facts come before the engine summary (after the
                    # opening line in an overview); the last-move check only when asked.
                    cited = [source for source in board_facts
                             if source.id == "T1" or re.search(LAST_MOVE_QUESTION, question, re.I)]
                    facts = "\n".join(f"{source.text} [{source.id}]" for source in cited)
                    parts = [opening_header] if mode == "overview" else []
                    advice = "\n\n".join([*parts, *([facts] if facts else []), grounded_advice])
            answer = CoachReply(f"{advice}\n\n（{reason}，以上為基礎回覆。）", [source.as_dict() for source in cited], mode)
            logger.info("Coach answer mode=fallback")
        else:
            logger.info("Coach answer mode=%s status=%s", mode, answer.status)
        return answer

    def get_advice(self, *args, **kwargs):
        """Text-only compatibility interface; APIs also expose citation details."""
        return self.get_response(*args, **kwargs).advice

_rag_engine = None


def get_rag_engine():
    global _rag_engine
    if _rag_engine is None:
        _rag_engine = ChessRAG()
    return _rag_engine
