"""Run beginner questions through /explain with a real model and score the answers.

Usage (needs GOOGLE_API_KEY; read from the environment or the repo's .env):
    PYTHONPATH=backend .venv/bin/python backend/eval_coach.py [--runs 2] [--only fools-mate-g4] [--out results.json]

Scores are cheap heuristics for comparing prompt or evidence changes, not proof
of quality. Read the answers too. Each run sends the positions and questions to
the configured Gemini models and uses the key's quota.
"""
import argparse
import json
import os
import pathlib
import re
import sys
import time

import chess

ROOT = pathlib.Path(__file__).resolve().parent
CASES = ROOT / "coach_eval_cases.json"
HABIT = re.compile(r"下次|以後|每次|養成|習慣|記得|先檢查|走之前|走棋前")
HEDGE = re.compile(r"尚未完成|無法判斷|無法確認|還不能確定|不能確定|暫時的方向|暫時方向")
TAGS = re.compile(r"\s*\[[A-Z]\d{1,2}\]")
MOVE = re.compile(r"(?<![A-Za-z0-9])(?:[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?|O-O(?:-O)?)(?![A-Za-z0-9])")


def load_env():
    if os.getenv("GOOGLE_API_KEY"):
        return
    env = ROOT.parent / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def position(moves):
    board = chess.Board()
    pgn = []
    for index, san in enumerate(moves.split()):
        if index % 2 == 0:
            pgn.append(f"{index // 2 + 1}.")
        pgn.append(san)
        board.push_san(san)
    return board.fen(), " ".join(pgn)


def score(case, data, seconds):
    text = TAGS.sub("", data.get("advice") or "")
    first = re.split(r"[。！？\n]", text.strip(), maxsplit=1)[0]
    must = case.get("must_mention") or []
    result = {
        "status": data.get("status"),
        "mode": data.get("mode"),
        "seconds": round(seconds, 1),
        "chars": len(text),
        "mentions_all": all(term in text for term in must),
        "conclusion_first": all(term in first for term in must[:1]),
        "has_habit": bool(HABIT.search(text)),
        "hedges": len(HEDGE.findall(text)),
        "uses_nin": "您" in text,
    }
    if case.get("expect_mode"):
        result["mode_ok"] = data.get("mode") == case["expect_mode"]
    if case.get("why_terms"):
        # Words that only appear when the answer explains the cause, e.g. the g3 block for 1.f3 e5 2.g4.
        result["explains_why"] = any(term in text for term in case["why_terms"])
    if case.get("forbid"):
        # Phrases that would mean the coach took the wrong side, e.g. telling White to play Black's move.
        result["forbid_ok"] = not any(phrase in text for phrase in case["forbid"])
    if case.get("no_moves"):
        result["no_moves_ok"] = not MOVE.search(text)
    return result, text


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--only", action="append", help="case id; repeatable")
    parser.add_argument("--out", help="write every answer and score as JSON")
    args = parser.parse_args()

    load_env()
    if not os.getenv("GOOGLE_API_KEY"):
        sys.exit("GOOGLE_API_KEY is not set (checked the environment and .env); nothing to evaluate.")
    os.environ.setdefault("ENABLE_CHROMA_RAG", "0")

    from fastapi.testclient import TestClient
    import api

    client = TestClient(api.app)
    cases = [case for case in json.loads(CASES.read_text(encoding="utf-8")) if not args.only or case["id"] in args.only]
    records = []
    for run in range(1, args.runs + 1):
        for case in cases:
            fen, history = position(case["moves"])
            body = {"fen": fen, "history": history, "question": case["question"], "player_color": case["player_color"]}
            started = time.monotonic()
            data = client.post("/explain", json=body).json()
            result, text = score(case, data, time.monotonic() - started)
            records.append({"run": run, "id": case["id"], **result, "answer": text})
            flags = " ".join(f"{key}={value}" for key, value in result.items() if key not in {"seconds", "chars"})
            print(f"\n[{run}] {case['id']} ({result['seconds']}s, {result['chars']} chars) {flags}\n{text}")

    total = len(records)
    generated = [r for r in records if r["status"] == "generated"]
    def rate(key, pool):
        rows = [r for r in pool if key in r]
        return f"{sum(bool(r[key]) for r in rows)}/{len(rows)}" if rows else "-"
    print("\n=== summary ===")
    print(f"generated        {len(generated)}/{total}")
    for key in ("mentions_all", "conclusion_first", "explains_why", "has_habit", "forbid_ok", "mode_ok", "no_moves_ok"):
        print(f"{key:<16} {rate(key, records)}")
    print(f"uses 您          {sum(r['uses_nin'] for r in records)}/{total}")
    print(f"hedges per answer {sum(r['hedges'] for r in records) / max(total, 1):.2f}")
    print(f"median seconds   {sorted(r['seconds'] for r in records)[total // 2] if total else '-'}")
    if args.out:
        pathlib.Path(args.out).write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
