import csv
import io
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import chess
import chess.pgn


DATA_DIR = Path(__file__).resolve().parent / "data" / "openings"

FAMILY_TRANSLATIONS = {
    "Alekhine Defense": "阿列欣防禦",
    "Benoni Defense": "貝諾尼防禦",
    "Bishop's Opening": "象開局",
    "Caro-Kann Defense": "卡羅康防禦",
    "Dutch Defense": "荷蘭防禦",
    "English Opening": "英國式開局",
    "French Defense": "法蘭西防禦",
    "Four Knights Game": "四馬開局",
    "Grünfeld Defense": "格林菲爾德防禦",
    "Indian Defense": "印度防禦",
    "Italian Game": "義大利開局",
    "King's Gambit Accepted": "國王棄兵接受變例",
    "King's Gambit Declined": "國王棄兵拒絕變例",
    "King's Indian Defense": "國王印度防禦",
    "London System": "倫敦系統",
    "Nimzo-Indian Defense": "尼姆佐印度防禦",
    "Nimzowitsch Defense": "尼姆佐維奇防禦",
    "Petrov's Defense": "彼得羅夫防禦",
    "Philidor Defense": "菲利多爾防禦",
    "Queen's Gambit": "后翼棄兵",
    "Queen's Gambit Accepted": "后翼棄兵接受變例",
    "Queen's Gambit Declined": "后翼棄兵拒絕變例",
    "Queen's Indian Defense": "后翼印度防禦",
    "Queen's Pawn Game": "后兵開局",
    "Réti Opening": "列蒂開局",
    "Ruy Lopez": "西班牙開局",
    "Scandinavian Defense": "斯堪地那維亞防禦",
    "Scotch Game": "蘇格蘭開局",
    "Semi-Slav Defense": "半斯拉夫防禦",
    "Sicilian Defense": "西西里防禦",
    "Slav Defense": "斯拉夫防禦",
    "Zukertort Opening": "祖克托爾夫開局",
}


@dataclass(frozen=True)
class OpeningRecord:
    eco: str
    name: str
    pgn: str
    plies: int

    @property
    def display_name(self):
        family = self.name.split(":", 1)[0].split(",", 1)[0]
        translated = FAMILY_TRANSLATIONS.get(family)
        if translated:
            return f"{self.eco} {translated}（{self.name}）"
        return f"{self.eco} {self.name}"


def _position_key(board):
    return " ".join(board.fen(en_passant="legal").split()[:4])


def _record_priority(record):
    return (record.plies, record.name.count(":"), record.name.count(","), len(record.name))


@lru_cache(maxsize=1)
def load_opening_index():
    index = {}
    paths = sorted(DATA_DIR.glob("[a-e].tsv"))
    if len(paths) != 5:
        raise RuntimeError(f"Expected five ECO data files in {DATA_DIR}, found {len(paths)}")

    for path in paths:
        with path.open(encoding="utf-8", newline="") as source:
            for row in csv.DictReader(source, delimiter="\t"):
                game = chess.pgn.read_game(io.StringIO(row["pgn"]))
                if not game:
                    continue

                board = game.board()
                plies = 0
                for move in game.mainline_moves():
                    board.push(move)
                    plies += 1

                record = OpeningRecord(
                    eco=row["eco"],
                    name=row["name"],
                    pgn=row["pgn"],
                    plies=plies,
                )
                key = _position_key(board)
                current = index.get(key)
                if current is None or _record_priority(record) > _record_priority(current):
                    index[key] = record

    return index


def identify_opening(move_history):
    if not move_history:
        return None

    try:
        game = chess.pgn.read_game(io.StringIO(move_history))
        if not game:
            return None

        board = game.board()
        positions = []
        for ply, move in enumerate(game.mainline_moves(), start=1):
            board.push(move)
            positions.append((ply, _position_key(board)))
    except (ValueError, TypeError, KeyError):
        return None

    index = load_opening_index()
    for matched_ply, position in reversed(positions):
        record = index.get(position)
        if record:
            return {
                "eco": record.eco,
                "name": record.display_name,
                "official_name": record.name,
                "matched_plies": matched_ply,
                "reference_pgn": record.pgn,
            }
    return None
