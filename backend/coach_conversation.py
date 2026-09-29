"""Bounded conversation context and conservative, local question routing."""

import re

import chess

MODES = {"knowledge", "position", "comparison", "hint", "overview"}
FOLLOW_UP = re.compile(r"^(那|所以|再|可以.{0,4}(簡單|詳細)|講簡單|說簡單|換個|為什麼[？?]?$|why[?]?$|simpler|explain more)", re.I)
MOVE_TOKEN = re.compile(r"(?<![A-Za-z0-9])(?:[a-h][1-8][a-h][1-8][qrbn]?|[KQRBN][a-h]?[1-8]?x?[a-h][1-8][+#]?|(?:[a-h]x)?[a-h][1-8](?:=[QRBN])?[+#]?|O-O(?:-O)?)(?![A-Za-z0-9])")


def wants_brief_answer(question):
    return bool(re.search(r"簡單|簡短|一句話|簡潔|brief|short|simpl", question or "", re.I))


def position_key(fen):
    try:
        return " ".join(chess.Board(fen).fen().split()[:4])
    except (ValueError, TypeError):
        return None


def current_conversation(conversation, fen):
    """Old messages resolve wording, never supply chess evidence."""
    key = position_key(fen)
    turns = []
    for turn in (conversation or [])[-8:]:
        if not isinstance(turn, dict) or turn.get("role") not in {"user", "model"}:
            continue
        if not key or position_key(turn.get("fen")) != key:
            continue
        text = turn.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        turns.append({
            "role": turn["role"], "text": text[:1500],
            "mode": turn.get("mode") if turn.get("mode") in MODES else "position",
        })
    return turns


def question_mode(question, conversation=None, mode="auto"):
    if mode in {"overview", "hint"}:
        return mode
    question = (question or "").strip()
    if not question:
        return "overview"
    if re.search(r"別.{0,6}答案|不要.{0,6}答案|don't.{0,12}answer", question, re.I):
        return "hint"
    if re.search(r"(直接|告訴我|給我|顯示|公布).{0,5}答案|show.{0,5}answer", question, re.I):
        return "position"
    if re.search(r"提示|別.{0,3}答案|不要.{0,3}答案|hint|don't.{0,8}answer", question, re.I):
        return "hint"
    if FOLLOW_UP.search(question) and conversation:
        return conversation[-1].get("mode", "position")
    if re.search(r"怎麼下|如何走|怎麼走", question) and not MOVE_TOKEN.search(question):
        return "position"
    if re.search(r"比較|哪個|哪一[手步個]|還是|compare|versus|\bvs\b", question, re.I) or len(MOVE_TOKEN.findall(question)) >= 2:
        return "comparison"
    if re.search(r"目前|現在|這[步手盤局個是]|我[的上]|剛才|局面|盤面|這裡|current|this (move|position)|can i", question, re.I) or MOVE_TOKEN.search(question):
        return "position"
    if re.search(r"是什麼|什麼是|規則|條件|意思|原理|為什麼要|如何|怎麼|what is|what are|why|how", question, re.I):
        if re.search(r"怎麼下|如何走|怎麼走", question):
            return "position"
        return "knowledge"
    return "position"


def retrieval_question(question, conversation):
    if not FOLLOW_UP.search(question or ""):
        return question
    prior = [turn["text"] for turn in conversation if turn["role"] == "user"]
    return " ".join([*prior[-2:], question])[:2000]
