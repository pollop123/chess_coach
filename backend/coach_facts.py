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
        attackers = _legal_attackers(board, not color, square)
        if not attackers:
            continue
        cheapest = min(VALUES[board.piece_at(s).piece_type] or 100 for s in attackers)
        if not board.attackers(color, square):
            loose.append((VALUES[piece.piece_type], square, "沒有保護"))
        elif cheapest < VALUES[piece.piece_type]:
            loose.append((VALUES[piece.piece_type], square, "會被價值較低的棋子吃掉"))
    return [(square, why) for _value, square, why in sorted(loose, key=lambda item: -item[0])]


def _legal_attackers(board, color, square):
    """Squares of `color` pieces that could legally capture on `square` (pinned pieces cannot)."""
    if board.turn == color:
        probe = board
    elif board.is_check():
        # No null move while in check; the side to move must answer the check first anyway.
        return set(board.attackers(color, square))
    else:
        probe = board.copy(stack=False)
        probe.push(chess.Move.null())
    return {move.from_square for move in probe.legal_moves if move.to_square == square}


def _free_captures(board):
    """Legal captures of undefended pieces for the side to move."""
    captures = []
    for move in board.legal_moves:
        target = board.piece_at(move.to_square)
        if target and target.color != board.turn and not board.attackers(not board.turn, move.to_square):
            captures.append((VALUES[target.piece_type], move))
    return [move for _value, move in sorted(captures, key=lambda item: -item[0])]


def _threats_against(board, color):
    """SAN of mates the opponent of `color` would have if it were their move."""
    if board.turn != color:
        return [board.san(move) for move in mating_moves(board)]
    if board.is_check():
        return []
    probe = board.copy(stack=False)
    probe.push(chess.Move.null())
    return [probe.san(move) for move in mating_moves(probe)]


def _squares(squares):
    return "、".join(chess.square_name(square) for square in squares)


def _line_kind(a, b):
    if chess.square_file(a) == chess.square_file(b):
        return "直線"
    if chess.square_rank(a) == chess.square_rank(b):
        return "橫線"
    return "斜線"


def _mate_threat(board, color):
    """(position, move) for a mate the opponent of `color` has, or would have if it were their move."""
    if board.turn != color:
        probe = board
    elif board.is_check():
        return None
    else:
        probe = board.copy(stack=False)
        probe.push(chess.Move.null())
    mates = mating_moves(probe)
    return (probe, mates[0]) if mates else None


def explain_mate(board, move):
    """Why `move` mates: the checking line, why nothing blocks or captures it, and where the king cannot go."""
    after = board.copy(stack=False)
    after.push(move)
    if not after.is_checkmate():
        return None
    defender, king = after.turn, after.king(after.turn)
    san = board.san(move)
    checkers = list(after.checkers())
    parts = []
    line = set()
    if len(checkers) > 1:
        parts.append(f"{san} 是雙將，王只能移動，而且沒有安全的格子")
    else:
        checker = checkers[0]
        piece = after.piece_at(checker)
        who = f"{SIDES[not defender]}的{NAMES[piece.piece_type]}在 {chess.square_name(checker)}，"
        line = set(chess.SquareSet(chess.between(checker, king)))
        if line:
            parts.append(f"{san} 之後，{who}沿著 {chess.square_name(checker)}–{chess.square_name(king)} 的"
                         f"{_line_kind(checker, king)}將軍，中間的 {_squares(sorted(line))} 沒有{SIDES[defender]}的棋子能擋")
        elif piece.piece_type == chess.KNIGHT:
            parts.append(f"{san} 之後，{who}將軍，馬的將軍不能被擋")
        else:
            parts.append(f"{san} 之後，{who}貼著王將軍")
        line.add(checker)  # covered by the capture sentence, not an escape square
        if chess.square_distance(checker, king) == 1:
            guards = after.attackers(not defender, checker)
            if guards:
                parts.append(f"王不能吃掉它，因為有{'、'.join(_piece_label(after, sq) for sq in guards)}保護")
    # Squares behind the king on the checking line are attacked through it, so look with the king lifted.
    lifted = after.copy(stack=False)
    lifted.remove_piece_at(king)
    own, controlled = [], []
    for square in chess.SquareSet(chess.BB_KING_ATTACKS[king]):
        occupant = after.piece_at(square)
        if occupant and occupant.color == defender:
            own.append(square)
        elif square not in line:
            attackers = lifted.attackers(not defender, square)
            if attackers:
                controlled.append(f"{chess.square_name(square)} 被{_piece_label(after, min(attackers))}控制")
    if own:
        parts.append(f"王旁邊的 {_squares(sorted(own))} 被自己的棋子堵住")
    if controlled:
        parts.append("、".join(controlled[:3]))
    return "；".join(parts) + "。"


def lost_defence(before, move, mate_move):
    """What `move` took away: a way to answer the mating check, or the king's escape square."""
    san = before.san(move)
    piece = NAMES[before.piece_at(move.from_square).piece_type]
    mated = before.copy(stack=False)
    mated.push(move)
    mated.push(mate_move)
    king = mated.king(mated.turn)
    if king is not None and move.to_square in chess.SquareSet(chess.BB_KING_ATTACKS[king]) \
            and move.from_square != king and not mated.attackers(not mated.turn, move.to_square):
        # The moved piece now sits on a square the king could otherwise have fled to.
        return f"{san} 讓{piece}佔住了 {chess.square_name(move.to_square)}，正好堵住王可以逃的格子。"
    if before.is_check():
        return None
    probe = before.copy(stack=False)
    probe.push(chess.Move.null())
    if mate_move not in probe.legal_moves:
        return None
    check_san = probe.san(mate_move)
    probe.push(mate_move)
    if not probe.is_check():
        return None
    if probe.is_checkmate():
        return f"這個將死威脅在 {san} 之前就已經存在，{san} 沒有處理它。"
    for answer in probe.legal_moves:
        if answer.from_square == move.from_square:
            target = chess.square_name(answer.to_square)
            action = f"吃掉 {target} 的將軍棋子" if probe.is_capture(answer) else (
                "避開" if probe.piece_at(answer.from_square).piece_type == chess.KING else f"走到 {target} 擋住將軍")
            return f"走 {san} 之前，就算對手走 {check_san.rstrip('+#')}+，{piece}還能{action}；{san} 之後這個防守就沒了。"
    return None


def _loose_reason(before, move, after, square, why):
    """Why a piece became loose: it walked onto an attacked square, or its defender moved away."""
    mover = before.turn
    attackers = _legal_attackers(after, not mover, square)
    if not attackers:
        return None
    attacker = min(attackers, key=lambda sq: VALUES[after.piece_at(sq).piece_type] or 100)
    target = _piece_label(after, square)
    if square == move.to_square:
        return (f"{NAMES[after.piece_at(square).piece_type]}走到 {chess.square_name(square)}，這格被"
                f"{_piece_label(after, attacker)}攻擊，而且{why}。")
    if move.from_square in before.attackers(mover, square) and move.from_square not in after.attackers(mover, square):
        return (f"原本保護{target}的{NAMES[before.piece_at(move.from_square).piece_type]}走開了，"
                f"現在{target}被{_piece_label(after, attacker)}攻擊，而且{why}。")
    return f"這步之後，{SIDES[mover]}的{target}被{_piece_label(after, attacker)}攻擊，而且{why}。"


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
    played, reached = [], None
    if _position_key(replay) == target:
        reached = 0
    # A repeated position must resolve to its latest occurrence, not the first.
    for move in game.mainline_moves():
        played.append((replay.copy(stack=False), move))
        replay.push(move)
        if _position_key(replay) == target:
            reached = len(played)
    return None if reached is None else played[:reached]


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
    if before.is_en_passant(move):
        captured = chess.Piece(chess.PAWN, not before.turn)
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
            problems.extend(text for text in (explain_mate(after, mates[0]), lost_defence(before, move, mates[0])) if text)
        before_loose = {square for square, _why in loose_pieces(before, mover)}
        # Taking something worth at least the capturing piece is a trade, not a blunder.
        traded = captured and VALUES[captured.piece_type] >= VALUES[before.piece_at(move.from_square).piece_type]
        for square, why in loose_pieces(after, mover):
            if square not in before_loose and not (traded and square == move.to_square):
                problems.append(_loose_reason(before, move, after, square, why)
                                or f"這步之後，{SIDES[mover]}的{_piece_label(after, square)}受到攻擊且{why}。")
                break
        missed_mates = [m for m in mating_moves(before) if m != move]
        if missed_mates:
            problems.append(f"這步之前，{SIDES[mover]}原本可以走 {before.san(missed_mates[0])} 直接將死。")
            problems.append(explain_mate(before, missed_mates[0]) or "")
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
        facts.append(explain_mate(board, mates[0]) or "")
    else:
        free = _free_captures(board)
        if free:
            target = board.piece_at(free[0].to_square)
            facts.append(f"{SIDES[side]}現在可以走 {board.san(free[0])} 吃掉沒有保護的{NAMES[target.piece_type]}。")
    threat = _mate_threat(board, side)
    if threat:
        probe, mate = threat
        facts.append(f"如果不處理，{SIDES[opponent]}下一步可以走 {probe.san(mate)} 將死。")
        facts.append(explain_mate(probe, mate) or "")
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


def threat_hint_source(board, student_color=None):
    """The same checks as threat_source, worded without moves or squares for hint mode.

    "你" is the student. Right after the student's own move the side to move is
    the opponent, so the wording flips instead of crediting the student with
    the opponent's chances.
    """
    if board.is_game_over():
        return None
    side = board.turn
    student_to_move = student_color is None or student_color == side
    hints = []
    if student_to_move:
        if board.is_check():
            hints.append("你正被將軍，先想想有哪些方法能解除將軍。")
        elif mating_moves(board):
            hints.append("你現在有一步就能將死對手的走法，先從將軍的走法找起。")
        if _threats_against(board, side):
            hints.append("對手下一步有將死你的威脅，先找出對手想走哪一步，再想怎麼防守。")
        if loose_pieces(board, side):
            hints.append("你有棋子受到攻擊而且保護不夠，先檢查自己每枚棋子的安全。")
        elif _free_captures(board):
            hints.append("對手有棋子沒有保護，看看能不能安全吃掉它。")
    else:
        if mating_moves(board):
            hints.append("輪到對手走，而對手現在有一步將死你的走法，先找出是哪一步。")
        if _free_captures(board):
            hints.append("輪到對手走，對手可以吃掉你沒有保護的棋子，先檢查你每枚棋子的安全。")
        if _threats_against(board, side):
            hints.append("你已經製造了一步將死的威脅，看看對手要怎麼防守。")
    return EvidenceSource("H2", "威脅提示", "".join(hints[:2]), "position") if hints else None
