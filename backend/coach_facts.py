"""Exact board facts for coaching: what a move allowed or missed, and current threats.

Everything here is computed from legal moves and attack maps, never from a search,
so each sentence is a certain fact rather than an engine opinion.
"""
import io

import chess
import chess.pgn

from coach_evidence import EvidenceSource

VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}
NAMES = {chess.PAWN: "兵", chess.KNIGHT: "馬", chess.BISHOP: "象", chess.ROOK: "車", chess.QUEEN: "后", chess.KING: "王"}
SIDES = {chess.WHITE: "白方", chess.BLACK: "黑方"}
LAST_MOVE_QUESTION = r"剛才|剛剛|上一步|上一手|前一步|那一?步|那一?手|last move|previous move|my move"


def _position_key(board):
    return " ".join(board.fen().split()[:4])


def _piece_label(board, square):
    piece = board.piece_at(square)
    return f"{NAMES[piece.piece_type]}（{chess.square_name(square)}）"


def mating_moves(board):
    mates = []
    for move in board.legal_moves:
        board.push(move)
        if board.is_checkmate():
            mates.append(move)
        board.pop()
    return mates


def loose_pieces(board, color):
    """Pieces of `color` that the opponent attacks and either nobody defends or a cheaper piece attacks."""
    loose = []
    for square, piece in board.piece_map().items():
        if piece.color != color or piece.piece_type == chess.KING:
            continue
        attackers = board.attackers(not color, square)
        if not attackers:
            continue
        cheapest = min(VALUES[board.piece_at(s).piece_type] or 100 for s in attackers)
        if not board.attackers(color, square):
            loose.append((VALUES[piece.piece_type], square, "沒有保護"))
        elif cheapest < VALUES[piece.piece_type]:
            loose.append((VALUES[piece.piece_type], square, "會被價值較低的棋子吃掉"))
    return [(square, why) for _value, square, why in sorted(loose, key=lambda item: -item[0])]


def _free_captures(board):
    """Legal captures of undefended pieces for the side to move."""
    captures = []
    for move in board.legal_moves:
        target = board.piece_at(move.to_square)
        if target and target.color != board.turn and not board.attackers(not board.turn, move.to_square):
            captures.append((VALUES[target.piece_type], move))
    return [move for _value, move in sorted(captures, key=lambda item: -item[0])]


def _threats_against(board, color):
    """Mates the opponent of `color` would have if it were their move."""
    if board.turn != color:
        return mating_moves(board)
    if board.is_check():
        return []
    probe = board.copy(stack=False)
    probe.push(chess.Move.null())
    return mating_moves(probe)


def replay_history(history, board):
    """(position before, move) pairs from the PGN, up to the displayed board; None if it never gets there."""
    if not history:
        return None
    try:
        game = chess.pgn.read_game(io.StringIO(history))
    except (ValueError, TypeError):
        return None
    if not game or game.errors:
        return None
    replay = game.board()
    target = _position_key(board)
    played = []
    if _position_key(replay) == target:
        return played
    for move in game.mainline_moves():
        played.append((replay.copy(stack=False), move))
        replay.push(move)
        if _position_key(replay) == target:
            return played
    return None


def last_move_source(history, board, player_color=None):
    played = replay_history(history, board)
    if not played:
        return None
    index = len(played) - 1
    if player_color is not None:
        while index >= 0 and played[index][0].turn != player_color:
            index -= 1
        if index < 0:
            return None
    before, move = played[index]
    mover, opponent = before.turn, not before.turn
    san = before.san(move)
    after = before.copy(stack=False)
    after.push(move)

    captured = before.piece_at(move.to_square)
    facts = [f"{SIDES[mover]}上一手是 {san}：{NAMES[before.piece_at(move.from_square).piece_type]}從 "
             f"{chess.square_name(move.from_square)} 走到 {chess.square_name(move.to_square)}"
             + (f"，吃掉{NAMES[captured.piece_type]}" if captured else "") + "。"]
    problems = []
    if after.is_checkmate():
        facts.append("這步直接將死對手。")
    else:
        mates = mating_moves(after)
        if mates:
            problems.append(f"這步之後，{SIDES[opponent]}可以走 {after.san(mates[0])} 直接將死。")
        before_loose = {square for square, _why in loose_pieces(before, mover)}
        for square, why in loose_pieces(after, mover):
            if square not in before_loose:
                problems.append(f"這步之後，{SIDES[mover]}的{_piece_label(after, square)}受到攻擊且{why}。")
                break
        missed_mates = [m for m in mating_moves(before) if m != move]
        if missed_mates:
            problems.append(f"這步之前，{SIDES[mover]}原本可以走 {before.san(missed_mates[0])} 直接將死。")
        elif not captured:
            free = _free_captures(before)
            if free:
                target = before.piece_at(free[0].to_square)
                problems.append(f"這步之前，{SIDES[mover]}原本可以走 {before.san(free[0])} 吃掉沒有保護的{NAMES[target.piece_type]}。")
    facts.extend(problems or ["直接檢查盤面：這步沒有讓對手一步將死，也沒有新留下受攻擊而無保護的棋子；是否為最佳手需另看引擎評估。"])
    if index + 1 < len(played):
        reply_before, reply = played[index + 1]
        facts.append(f"{SIDES[opponent]}實際回應 {reply_before.san(reply)}。")
    return EvidenceSource("L1", "上一手檢查", "".join(facts), "position")


def threat_source(board):
    if board.is_game_over():
        return None
    side, opponent = board.turn, not board.turn
    facts = []
    mates = mating_moves(board)
    if mates:
        facts.append(f"{SIDES[side]}現在可以走 {board.san(mates[0])} 直接將死。")
    else:
        free = _free_captures(board)
        if free:
            target = board.piece_at(free[0].to_square)
            facts.append(f"{SIDES[side]}現在可以走 {board.san(free[0])} 吃掉沒有保護的{NAMES[target.piece_type]}。")
    threats = _threats_against(board, side)
    if threats:
        facts.append(f"如果不處理，{SIDES[opponent]}有一步將死的威脅。")
    loose = loose_pieces(board, side)
    if loose:
        square, why = loose[0]
        facts.append(f"{SIDES[side]}的{_piece_label(board, square)}受到攻擊且{why}。")
    if board.is_check():
        facts.insert(0, f"{SIDES[side]}正被將軍，必須先解將。")
    if not facts:
        facts.append(f"直接檢查盤面：{SIDES[side]}目前沒有一步將死的機會，也沒有受攻擊而無保護的棋子。")
    return EvidenceSource("T1", "目前威脅檢查", "".join(facts), "position")


def move_fact_summary(board, move):
    """One plain sentence about a legal move's certain effects, or None when it has none worth saying."""
    if move not in board.legal_moves:
        return None
    san = board.san(move)
    captured = board.piece_at(move.to_square)
    if board.is_en_passant(move):
        captured = chess.Piece(chess.PAWN, not board.turn)
    after = board.copy(stack=False)
    after.push(move)
    if after.is_checkmate():
        return f"{san} 直接將死。"
    parts = []
    if captured:
        parts.append(f"吃掉{NAMES[captured.piece_type]}")
    if after.is_check():
        parts.append("將軍")
    return f"{san} 會{'並'.join(parts)}。" if parts else None
