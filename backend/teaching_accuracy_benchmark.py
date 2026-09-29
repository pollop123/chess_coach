"""Independent Stockfish oracle for teaching-candidate accuracy."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

import chess
import chess.engine

import chess_engine
from evaluation import CALIBRATED_FEATURE_WEIGHTS, PositionEvaluator
from validate_training_lessons import find_stockfish


PROFILE_RELEASE = "release"
PROFILE_SMOKE = "smoke"
DEFAULT_RELEASE_NODES = 50_000
DEFAULT_SMOKE_NODES = 10_000
DEFAULT_CACHE_PATH = Path(__file__).resolve().parent / ".cache" / "teaching_accuracy_stockfish.json"
DEFAULT_SMOKE_ORACLE_FIXTURE = (
    Path(__file__).resolve().parent / "calibration" / "teaching-oracle-smoke.json"
)
SMOKE_POSITION_NAMES = (
    "two_knights_tactic",
    "queen_safety",
    "starting_position",
    "italian_two_knights",
    "center_pressure",
    "fen_only_middlegame",
    "rook_activity",
    "king_opposition",
)


class OracleMiss(LookupError):
    """A strict oracle lookup found no frozen answer for a query."""


class StockfishOracleCache:
    """Persistent store for deterministic, node-limited Stockfish queries.

    Entries are keyed by the query alone; the engine build that produced them
    is recorded once in the file header. Two Stockfish builds report the same
    UCI id, so the header carries the binary digest and a file written by a
    different build is discarded rather than silently reused.

    A read-only, strict instance backed by a committed file turns this into a
    frozen oracle fixture: every answer is pinned, and a query the fixture does
    not cover raises instead of quietly consulting whatever engine is present.
    """

    SCHEMA_VERSION = 2

    def __init__(
        self,
        path: str | Path = DEFAULT_CACHE_PATH,
        *,
        enabled: bool = True,
        refresh: bool = False,
        readonly: bool = False,
        strict: bool = False,
        engine_identity: str | None = None,
    ) -> None:
        self.path = Path(path)
        self.enabled = enabled
        self.refresh = refresh
        self.readonly = readonly
        self.strict = strict
        self.engine_identity = engine_identity
        self.source_engine: str | None = None
        self.entries: dict[str, dict[str, Any]] = {}
        self.hits = 0
        self.misses = 0
        self.writes = 0
        self._dirty = False
        if enabled:
            self._load()

    @staticmethod
    def _digest(query: dict[str, Any]) -> str:
        payload = json.dumps(query, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _load(self) -> None:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            if self.strict:
                raise OracleMiss(
                    f"oracle fixture is missing or unreadable: {self.path}"
                ) from None
            return
        if payload.get("schema_version") != self.SCHEMA_VERSION:
            if self.strict:
                raise OracleMiss(
                    f"oracle fixture {self.path} has schema_version "
                    f"{payload.get('schema_version')!r}, expected {self.SCHEMA_VERSION}"
                )
            return
        self.source_engine = payload.get("engine")
        # A file written by a different Stockfish build answers the same
        # queries differently, so reuse it only when the builds match.
        if (
            self.engine_identity is not None
            and self.source_engine is not None
            and self.source_engine != self.engine_identity
        ):
            return
        entries = payload.get("entries")
        if isinstance(entries, dict):
            self.entries = entries

    def get(self, query: dict[str, Any]) -> Any | None:
        if not self.enabled or self.refresh:
            self.misses += 1
            if self.strict:
                raise OracleMiss(self._miss_message(query))
            return None
        entry = self.entries.get(self._digest(query))
        if not isinstance(entry, dict) or entry.get("query") != query:
            self.misses += 1
            if self.strict:
                raise OracleMiss(self._miss_message(query))
            return None
        self.hits += 1
        return entry.get("value")

    def _miss_message(self, query: dict[str, Any]) -> str:
        move = query.get("move")
        move_hint = f" move={move}" if move else ""
        return (
            f"no frozen oracle answer in {self.path} for "
            f"{query.get('kind')} nodes={query.get('nodes')} fen={query.get('fen')!r}"
            f"{move_hint}"
            "\nRegenerate the fixture with --write-oracle-fixture using a"
            " Stockfish binary, then commit the result."
        )

    def set(self, query: dict[str, Any], value: Any) -> None:
        if not self.enabled or self.readonly:
            return
        self.entries[self._digest(query)] = {"query": query, "value": value}
        self.writes += 1
        self._dirty = True

    def save(self) -> None:
        if not self.enabled or self.readonly or not self._dirty:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "engine": self.engine_identity or self.source_engine,
            "entries": self.entries,
        }
        temporary_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        os.replace(temporary_path, self.path)
        self._dirty = False

    def stats(self) -> dict[str, int | bool | str | None]:
        return {
            "enabled": self.enabled,
            "path": str(self.path),
            "frozen": self.readonly,
            "source_engine": self.source_engine,
            "hits": self.hits,
            "misses": self.misses,
            "writes": self.writes,
        }


@dataclass(frozen=True)
class AccuracyPosition:
    name: str
    fen: str
    topic: str
    depth: int = 3
    candidate_count: int = 6
    game_id: str | None = None
    split: str | None = None


def _fen_after(*sans: str) -> str:
    board = chess.Board()
    for san in sans:
        board.push_san(san)
    return board.fen()


POSITIONS = (
    AccuracyPosition(
        "scholar_mate_finish",
        "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4",
        "tactics",
    ),
    AccuracyPosition(
        "two_knights_tactic",
        "r1bqkb1r/ppp2ppp/2n5/3np1N1/2B5/8/PPPP1PPP/RNBQK2R w KQkq - 0 6",
        "tactics",
    ),
    AccuracyPosition("queen_mate_net", "7k/8/5KQ1/8/8/8/8/8 w - - 0 1", "tactics"),
    AccuracyPosition("queen_safety", "7r/4k2p/8/7Q/8/8/8/4K3 w - - 0 1", "tactics"),
    AccuracyPosition("rook_activity", "8/5pk1/6p1/3R4/7P/6P1/5PK1/r7 w - - 0 1", "endgame"),
    AccuracyPosition("king_opposition", "8/8/4k3/8/4P3/4K3/8/8 w - - 0 1", "endgame"),
    AccuracyPosition("black_back_rank_mate", "r5k1/5ppp/8/8/8/8/5PPP/6K1 b - - 0 1", "tactics"),
    AccuracyPosition("starting_position", chess.STARTING_FEN, "opening"),
    AccuracyPosition("italian_two_knights", _fen_after("e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6"), "opening"),
    AccuracyPosition("london_setup", _fen_after("d4", "d5", "Nf3", "Nf6", "Bf4"), "opening"),
    AccuracyPosition(
        "sicilian_setup",
        _fen_after("e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6"),
        "opening",
    ),
    AccuracyPosition(
        "caro_kann_setup",
        _fen_after("e4", "c6", "d4", "d5", "Nc3", "dxe4", "Nxe4", "Bf5"),
        "opening",
    ),
    AccuracyPosition(
        "center_pressure",
        "r1bqk2r/ppp2ppp/2np1n2/2b1p3/2B1P3/3P1N2/PPP2PPP/RNBQ1RK1 w kq - 0 6",
        "positional",
    ),
    AccuracyPosition(
        "center_break",
        "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2P2N2/PP1P1PPP/RNBQ1RK1 w kq - 4 5",
        "positional",
    ),
    AccuracyPosition(
        "pin_pressure",
        "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/2N2N2/PPPP1PPP/R1BQKB1R w KQkq - 2 3",
        "positional",
    ),
    AccuracyPosition(
        "fen_only_middlegame",
        "r1bq1rk1/pp2bppp/2n1pn2/2pp4/3P4/2P1PN2/PP1NBPPP/R2Q1RK1 w - - 0 22",
        "positional",
    ),
    AccuracyPosition("white_back_rank_mate", "6k1/5ppp/8/8/8/8/5PPP/R5K1 w - - 0 1", "tactics"),
    AccuracyPosition("pawn_promotion", "8/4P3/4K3/8/8/8/8/4k3 w - - 0 1", "endgame"),
    AccuracyPosition("king_activation", "8/8/5k2/8/4P3/4K3/8/8 w - - 0 1", "endgame"),
    AccuracyPosition("lucena_bridge", "1K1k4/1P6/8/8/8/8/r7/2R5 w - - 4 1", "endgame"),
    AccuracyPosition("free_queen_capture", "4k3/3q4/8/8/8/8/8/3Q2K1 w - - 0 1", "tactics"),
    AccuracyPosition("verified_knight_fork", "3qk2r/8/8/6N1/8/8/8/4K3 w - - 0 1", "tactics"),
    AccuracyPosition(
        "queenless_development",
        "rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNB1KBNR w KQkq - 0 1",
        "positional",
    ),
)


def select_positions(
    profile: str = PROFILE_RELEASE,
    topics: tuple[str, ...] | list[str] | None = None,
    positions: tuple[AccuracyPosition, ...] | None = None,
) -> tuple[AccuracyPosition, ...]:
    source = POSITIONS if positions is None else positions
    selected_topics = set(topics or ())
    selected = tuple(
        position
        for position in source
        if not selected_topics or position.topic in selected_topics
    )
    if profile == PROFILE_RELEASE or selected_topics:
        return selected
    if source is not POSITIONS:
        per_topic: dict[str, list[AccuracyPosition]] = {}
        for position in selected:
            per_topic.setdefault(position.topic, []).append(position)
        return tuple(
            position
            for topic in sorted(per_topic)
            for position in per_topic[topic][:2]
        )
    smoke_names = set(SMOKE_POSITION_NAMES)
    return tuple(position for position in selected if position.name in smoke_names)


def load_corpus(
    path: str | Path,
    splits: tuple[str, ...] | list[str] | None = None,
) -> tuple[AccuracyPosition, ...]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or not isinstance(payload.get("positions"), list):
        raise ValueError("Unsupported evaluation corpus schema")
    selected_splits = set(splits or ())
    positions = []
    for item in payload["positions"]:
        if selected_splits and item.get("split") not in selected_splits:
            continue
        position = AccuracyPosition(
            name=str(item["name"]),
            fen=str(item["fen"]),
            topic=str(item["topic"]),
            game_id=str(item["game_id"]),
            split=str(item["split"]),
        )
        board = chess.Board(position.fen)
        if not board.is_valid() or board.is_game_over(claim_draw=True):
            raise ValueError(f"Invalid or finished corpus position: {position.name}")
        positions.append(position)
    if not positions:
        raise ValueError("No corpus positions matched the requested split")
    return tuple(positions)


def limit_positions_per_topic(
    positions: tuple[AccuracyPosition, ...], limit: int | None
) -> tuple[AccuracyPosition, ...]:
    """Take a deterministic, corpus-ordered screening subset per topic."""
    if limit is None:
        return positions
    if limit <= 0:
        raise ValueError("Position limit per topic must be positive")
    counts: dict[str, int] = {}
    selected = []
    for position in positions:
        count = counts.get(position.topic, 0)
        if count >= limit:
            continue
        selected.append(position)
        counts[position.topic] = count + 1
    return tuple(selected)


def profile_search_settings(position: AccuracyPosition, profile: str) -> dict[str, int | bool]:
    if profile == PROFILE_SMOKE:
        return {
            "depth": min(2, position.depth),
            "candidate_count": min(3, position.candidate_count),
            "adaptive_depth": False,
        }
    return {
        "depth": position.depth,
        "candidate_count": position.candidate_count,
        "adaptive_depth": True,
    }


def parse_feature_weights(values: list[str] | None) -> dict[str, int]:
    """Parse repeatable NAME=PERCENT overrides for offline joint calibration."""
    weights: dict[str, int] = {}
    for value in values or ():
        try:
            name, raw_weight = value.split("=", 1)
            weight = int(raw_weight)
        except (ValueError, TypeError) as exc:
            raise ValueError(
                f"Invalid feature weight {value!r}; expected NAME=PERCENT"
            ) from exc
        if name not in CALIBRATED_FEATURE_WEIGHTS:
            allowed = ", ".join(sorted(CALIBRATED_FEATURE_WEIGHTS))
            raise ValueError(f"Unknown feature {name!r}; choose from: {allowed}")
        if not -200 <= weight <= 200:
            raise ValueError(f"Feature weight {name!r} must be between -200 and 200")
        weights[name] = weight
    return weights


def binary_digest(path: str | Path | None) -> str:
    """SHA-256 of the engine binary, or "unknown" when it cannot be read."""
    if not path:
        return "unknown"
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return "unknown"
    return digest.hexdigest()


def stockfish_signature(
    engine: chess.engine.SimpleEngine, path: str | Path | None = None
) -> str:
    """Identify the exact binary, not just the release it claims to be.

    Stockfish reports the same UCI id from every build, but a macOS arm64 and
    a Linux x86-64 avx2 build of one release return different moves at the same
    node budget, so the digest is what makes an oracle answer attributable.
    """
    identity = engine.id or {}
    fields = [f"{key}={identity[key]}" for key in sorted(identity)]
    fields.append(f"sha256={binary_digest(path)}")
    return "|".join(fields)


def _oracle_query(
    *,
    board: chess.Board,
    nodes: int,
    kind: str,
    multipv: int | None = None,
    move: chess.Move | None = None,
) -> dict[str, Any]:
    return {
        "fen": board.fen(),
        "nodes": nodes,
        "kind": kind,
        "multipv": multipv,
        "move": move.uci() if move else None,
        "score_perspective": "side_to_move",
        "mate_score": 100_000,
    }


class LazyStockfish:
    """Start Stockfish only when an oracle answer is not already frozen.

    A fully covered fixture never touches this, so a strict run needs no engine
    installed at all.
    """

    def __init__(self, path: str | Path | None) -> None:
        self.path = path
        self.identity: str | None = None
        self._engine: chess.engine.SimpleEngine | None = None

    def __call__(self) -> chess.engine.SimpleEngine:
        if self._engine is None:
            if not self.path:
                raise OracleMiss(
                    "an oracle answer is missing and no Stockfish binary is available"
                )
            self._engine = chess.engine.SimpleEngine.popen_uci(self.path)
            # Pin the search-affecting options rather than inheriting whatever
            # the installed build defaults to.
            self._engine.configure({"Threads": 1, "Hash": 16})
            self.identity = stockfish_signature(self._engine, self.path)
        return self._engine

    def close(self) -> None:
        if self._engine is not None:
            self._engine.quit()
            self._engine = None


def oracle_top_lines(
    engine: LazyStockfish,
    board: chess.Board,
    nodes: int,
    multipv: int,
    cache: StockfishOracleCache,
) -> tuple[list[chess.Move], list[int]]:
    # Every query passes a fresh game so python-chess sends ucinewgame: without
    # it Stockfish carries its hash between positions and an answer depends on
    # which unrelated position ran first, exactly the independence the local
    # engine already gets from reset_transposition_table().
    query = _oracle_query(
        board=board,
        nodes=nodes,
        kind="top_lines",
        multipv=multipv,
    )
    cached = cache.get(query)
    if isinstance(cached, dict):
        try:
            moves = [chess.Move.from_uci(value) for value in cached["moves"]]
            scores = [int(value) for value in cached["scores"]]
            if len(moves) == len(scores) and all(move in board.legal_moves for move in moves):
                return moves, scores
        except (KeyError, TypeError, ValueError):
            pass

    analysis = engine().analyse(
        board,
        chess.engine.Limit(nodes=nodes),
        multipv=multipv,
        game=object(),
    )
    moves = [item["pv"][0] for item in analysis if item.get("pv")]
    scores = [
        item["score"].pov(board.turn).score(mate_score=100_000) or 0
        for item in analysis
        if item.get("pv")
    ]
    cache.set(
        query,
        {"moves": [move.uci() for move in moves], "scores": scores},
    )
    return moves, scores


def oracle_forced_score(
    engine: LazyStockfish,
    board: chess.Board,
    move: chess.Move,
    nodes: int,
    cache: StockfishOracleCache,
) -> int:
    query = _oracle_query(
        board=board,
        nodes=nodes,
        kind="forced_move",
        move=move,
    )
    cached = cache.get(query)
    if isinstance(cached, int):
        return cached

    analysis = engine().analyse(
        board,
        chess.engine.Limit(nodes=nodes),
        root_moves=[move],
        game=object(),
    )
    score = analysis["score"].pov(board.turn).score(mate_score=100_000) or 0
    cache.set(query, int(score))
    return int(score)


def inversion_rate(scores_in_reported_order: list[int], tolerance_cp: int = 20) -> float:
    comparisons = 0
    inversions = 0
    for index, score in enumerate(scores_in_reported_order):
        for later_score in scores_in_reported_order[index + 1:]:
            comparisons += 1
            if later_score > score + tolerance_cp:
                inversions += 1
    return inversions / comparisons if comparisons else 0.0


def accuracy_gate(
    top3_rate: float,
    recall_rate: float,
    inversion: float,
    completion_rate: float,
    mean_loss_error_cp: float,
    mate_type_rate: float,
    only_move_precision: float,
    only_move_recall: float,
    loss_field_rate: float,
    max_position_loss_mae_cp: float,
    position_count: int,
    min_topic_top3_rate: float,
    min_topic_recall_rate: float,
) -> bool:
    """Strict release gate; ordinary benchmark runs may report without enforcing it."""
    return (
        position_count >= 20
        and top3_rate >= 0.9
        and recall_rate >= 0.9
        and min_topic_top3_rate >= 0.8
        and min_topic_recall_rate >= 0.8
        and inversion <= 0.15
        and completion_rate == 1.0
        and mean_loss_error_cp <= 100
        and mate_type_rate == 1.0
        and only_move_precision >= 0.95
        and only_move_recall >= 0.9
        and loss_field_rate == 1.0
        and max_position_loss_mae_cp <= 200
    )


def candidate_consistency(candidates: list[dict], forced_scores: list[int]) -> dict:
    if not candidates or not forced_scores:
        return {"loss_errors": [], "loss_fields_complete": False, "type_matches": False}
    candidate_best_score = max(forced_scores)
    oracle_best_is_mate = abs(candidate_best_score) >= 90_000
    loss_errors = []
    loss_fields_complete = True
    type_matches = True
    for item, forced_score in zip(candidates, forced_scores):
        oracle_is_mate = abs(forced_score) >= 90_000
        reported_is_mate = item.get("score_type") == "mate"
        # A shallow custom search may not see every distant forced mate, but it must
        # never label a centipawn oracle line as mate.
        type_matches = type_matches and (not reported_is_mate or oracle_is_mate)
        if oracle_best_is_mate or oracle_is_mate:
            continue
        reported_loss = item.get("loss_cp")
        if not isinstance(reported_loss, (int, float)):
            loss_fields_complete = False
            continue
        oracle_loss = max(0, candidate_best_score - forced_score)
        loss_errors.append(abs(reported_loss - oracle_loss))
    return {
        "loss_errors": loss_errors,
        "loss_fields_complete": loss_fields_complete,
        "type_matches": type_matches,
    }


def run(
    stockfish_path: str,
    nodes: int = DEFAULT_RELEASE_NODES,
    *,
    profile: str = PROFILE_RELEASE,
    topics: tuple[str, ...] | list[str] | None = None,
    cache_path: str | Path = DEFAULT_CACHE_PATH,
    use_cache: bool = True,
    refresh_cache: bool = False,
    feature_weights: dict[str, int] | None = None,
    positions: tuple[AccuracyPosition, ...] | None = None,
    oracle_fixture: str | Path | None = None,
    strict_oracle: bool = False,
) -> dict:
    if profile not in {PROFILE_RELEASE, PROFILE_SMOKE}:
        raise ValueError(f"Unknown benchmark profile: {profile}")

    benchmark_positions = select_positions(profile, topics, positions)
    if not benchmark_positions:
        raise ValueError("No benchmark positions matched the selected profile/topics")

    started_at = perf_counter()
    engine = LazyStockfish(stockfish_path)
    if oracle_fixture:
        # Frozen answers: read-only, and a gap is an error rather than a
        # silent recomputation against whichever build happens to be present.
        cache = StockfishOracleCache(
            oracle_fixture,
            readonly=True,
            strict=strict_oracle,
        )
    else:
        cache = StockfishOracleCache(
            cache_path,
            enabled=use_cache,
            refresh=refresh_cache,
            engine_identity=stockfish_signature(engine(), stockfish_path),
        )
    active_weights = dict(CALIBRATED_FEATURE_WEIGHTS)
    if feature_weights:
        active_weights.update(feature_weights)
    engine_session = chess_engine.EngineSession(
        evaluator=PositionEvaluator(active_weights)
    )
    activation = engine_session.activate()
    activation.__enter__()
    results = []
    try:
        for position in benchmark_positions:
            # Calibration positions must be independent. Reusing search
            # entries across fixtures makes topic-only and full-corpus runs
            # disagree based on which unrelated position ran first.
            chess_engine.reset_transposition_table()
            board = chess.Board(position.fen)
            multipv = min(3, board.legal_moves.count())
            oracle_top, oracle_scores = oracle_top_lines(
                engine,
                board,
                nodes,
                multipv,
                cache,
            )
            oracle_best = oracle_top[0]

            settings = profile_search_settings(position, profile)
            base = chess_engine.get_analysis(
                board,
                depth=int(settings["depth"]),
                adaptive_depth=bool(settings["adaptive_depth"]),
            )
            teaching = chess_engine.get_teaching_analysis(
                board,
                base,
                candidate_count=int(settings["candidate_count"]),
                depth=int(settings["depth"]),
            )
            candidates = teaching.get("candidates") or []
            candidate_moves = [chess.Move.from_uci(item["move"]) for item in candidates]
            forced_scores = [
                oracle_forced_score(
                    engine,
                    board,
                    move,
                    nodes,
                    cache,
                )
                for move in candidate_moves
            ]

            reported_top = candidate_moves[0] if candidate_moves else None
            consistency = candidate_consistency(candidates, forced_scores)
            loss_errors = consistency["loss_errors"]
            oracle_gap = (
                max(0, oracle_scores[0] - oracle_scores[1])
                if len(oracle_scores) >= 2
                else 100_000
            )
            oracle_only_move = oracle_gap >= 150
            reported_only_move = teaching.get("criticality") == "only_move"
            oracle_top_is_mate = abs(oracle_scores[0]) >= 90_000
            reported_top_is_mate = bool(
                candidates and candidates[0].get("score_type") == "mate"
            )
            mate_type_matches = consistency["type_matches"] and (
                not oracle_top_is_mate or reported_top_is_mate
            )
            results.append({
                "name": position.name,
                "topic": position.topic,
                "oracle_best": board.san(oracle_best),
                "oracle_top": [board.san(move) for move in oracle_top],
                "reported_top": board.san(reported_top) if reported_top else None,
                "top_in_oracle_top3": reported_top in oracle_top,
                "oracle_best_recalled": oracle_best in candidate_moves,
                "rank_inversion_rate": round(inversion_rate(forced_scores), 4),
                "candidate_loss_mae_cp": (
                    round(sum(loss_errors) / len(loss_errors), 1)
                    if loss_errors
                    else None
                ),
                "loss_errors_cp": loss_errors,
                "mate_type_matches": mate_type_matches,
                "loss_fields_complete": consistency["loss_fields_complete"],
                "oracle_only_move": oracle_only_move,
                "reported_criticality": teaching.get("criticality"),
                "only_move_matches": oracle_only_move == reported_only_move,
                "analysis_complete": teaching.get("analysis_complete"),
            })
    finally:
        activation.__exit__(None, None, None)
        engine.close()
        cache.save()

    count = len(results)
    top3_rate = sum(item["top_in_oracle_top3"] for item in results) / count
    recall_rate = sum(item["oracle_best_recalled"] for item in results) / count
    average_inversion_rate = sum(item["rank_inversion_rate"] for item in results) / count
    completion_rate = sum(bool(item["analysis_complete"]) for item in results) / count
    all_loss_errors = [
        error for item in results for error in item["loss_errors_cp"]
    ]
    mean_loss_error_cp = sum(all_loss_errors) / len(all_loss_errors) if all_loss_errors else 0.0
    mate_type_rate = sum(item["mate_type_matches"] for item in results) / count
    only_move_true_positives = sum(
        item["oracle_only_move"] and item["reported_criticality"] == "only_move"
        for item in results
    )
    only_move_reported = sum(item["reported_criticality"] == "only_move" for item in results)
    only_move_oracle = sum(item["oracle_only_move"] for item in results)
    only_move_precision = (
        only_move_true_positives / only_move_reported if only_move_reported else 1.0
    )
    only_move_recall = (
        only_move_true_positives / only_move_oracle if only_move_oracle else 1.0
    )
    loss_field_rate = sum(item["loss_fields_complete"] for item in results) / count
    position_loss_maes = [
        item["candidate_loss_mae_cp"]
        for item in results
        if item["candidate_loss_mae_cp"] is not None
    ]
    max_position_loss_mae_cp = max(position_loss_maes, default=0.0)
    topic_metrics = {}
    for topic in sorted({item["topic"] for item in results}):
        topic_results = [item for item in results if item["topic"] == topic]
        topic_count = len(topic_results)
        topic_metrics[topic] = {
            "positions": topic_count,
            "top3_rate": round(
                sum(item["top_in_oracle_top3"] for item in topic_results) / topic_count,
                3,
            ),
            "recall_rate": round(
                sum(item["oracle_best_recalled"] for item in topic_results) / topic_count,
                3,
            ),
        }
    min_topic_top3_rate = min(
        (metrics["top3_rate"] for metrics in topic_metrics.values()), default=0.0
    )
    min_topic_recall_rate = min(
        (metrics["recall_rate"] for metrics in topic_metrics.values()), default=0.0
    )
    passed = accuracy_gate(
        top3_rate,
        recall_rate,
        average_inversion_rate,
        completion_rate,
        mean_loss_error_cp,
        mate_type_rate,
        only_move_precision,
        only_move_recall,
        loss_field_rate,
        max_position_loss_mae_cp,
        count,
        min_topic_top3_rate,
        min_topic_recall_rate,
    )
    return {
        "mode": "stockfish_accuracy",
        "profile": profile,
        "topics": sorted(set(topics or ())),
        "stockfish": stockfish_path,
        "stockfish_signature": engine.identity or cache.source_engine,
        "nodes": nodes,
        "feature_weights": active_weights,
        "duration_seconds": round(perf_counter() - started_at, 3),
        "oracle_cache": cache.stats(),
        "positions": count,
        "data_splits": sorted(
            {position.split for position in benchmark_positions if position.split}
        ),
        "game_groups": len(
            {position.game_id for position in benchmark_positions if position.game_id}
        ),
        "top1_in_oracle_top3_rate": round(top3_rate, 3),
        "oracle_best_recall_rate": round(recall_rate, 3),
        "average_rank_inversion_rate": round(average_inversion_rate, 3),
        "analysis_completion_rate": round(completion_rate, 3),
        "mean_candidate_loss_error_cp": round(mean_loss_error_cp, 1),
        "mate_score_type_precision_rate": round(mate_type_rate, 3),
        "only_move_precision": round(only_move_precision, 3),
        "only_move_recall": round(only_move_recall, 3),
        "loss_field_completion_rate": round(loss_field_rate, 3),
        "max_position_loss_mae_cp": round(max_position_loss_mae_cp, 1),
        "by_topic": topic_metrics,
        "minimum_topic_top3_rate": min_topic_top3_rate,
        "minimum_topic_recall_rate": min_topic_recall_rate,
        "thresholds": {
            "minimum_positions": 20,
            "top3_rate": 0.9,
            "recall_rate": 0.9,
            "minimum_topic_top3_rate": 0.8,
            "minimum_topic_recall_rate": 0.8,
            "max_inversion_rate": 0.15,
            "completion_rate": 1.0,
            "max_mean_loss_error_cp": 100,
            "mate_type_rate": 1.0,
            "only_move_precision": 0.95,
            "only_move_recall": 0.9,
            "loss_field_rate": 1.0,
            "max_position_loss_mae_cp": 200,
        },
        "release_ready": passed,
        "passed": passed,
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stockfish")
    parser.add_argument(
        "--profile",
        choices=(PROFILE_SMOKE, PROFILE_RELEASE),
        default=PROFILE_RELEASE,
        help="smoke uses fewer positions/candidates and disables adaptive depth",
    )
    parser.add_argument(
        "--topic",
        action="append",
        choices=("opening", "tactics", "positional", "endgame"),
        help="limit the run to one or more topics; may be repeated",
    )
    parser.add_argument(
        "--nodes",
        type=int,
        help="Stockfish nodes per query (defaults: smoke=10000, release=50000)",
    )
    parser.add_argument("--cache-path", default=str(DEFAULT_CACHE_PATH))
    parser.add_argument("--corpus", help="JSON corpus generated by build_evaluation_corpus.py")
    parser.add_argument(
        "--split",
        action="append",
        choices=("train", "validation", "test"),
        help="limit an external corpus to one or more game-grouped splits",
    )
    parser.add_argument(
        "--limit-per-topic",
        type=int,
        help="deterministic screening limit for each topic in an external corpus",
    )
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument(
        "--feature-weight",
        action="append",
        default=[],
        metavar="NAME=PERCENT",
        help="override an evaluator feature weight; repeat to calibrate jointly",
    )
    parser.add_argument(
        "--oracle-fixture",
        help="read every oracle answer from this committed fixture instead of the"
        " mutable cache",
    )
    parser.add_argument(
        "--strict-oracle",
        action="store_true",
        help="fail on any oracle answer the fixture does not cover, instead of"
        " recomputing it with whichever Stockfish build is installed"
        f" (default fixture: {DEFAULT_SMOKE_ORACLE_FIXTURE.name})",
    )
    parser.add_argument(
        "--write-oracle-fixture",
        metavar="PATH",
        help="run against a real Stockfish and write the answers to PATH as a"
        " frozen fixture; commit the result",
    )
    parser.add_argument(
        "--refresh-cache",
        action="store_true",
        help="ignore matching reads and replace them with fresh Stockfish results",
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", help="write the complete JSON report to this path")
    parser.add_argument(
        "--require-release-ready",
        action="store_true",
        help="Exit non-zero when the strict release gate is not satisfied.",
    )
    args = parser.parse_args()
    if args.no_cache and args.refresh_cache:
        parser.error("--no-cache and --refresh-cache cannot be used together")
    if args.require_release_ready and (
        args.profile != PROFILE_RELEASE
        or args.topic
        or args.corpus
        or args.split
        or args.limit_per_topic
    ):
        # The strict gate must certify the full release corpus. Allowing an
        # external corpus or any subset selector would let a tuned slice exit
        # zero and advertise release readiness the full set never earned.
        parser.error("--require-release-ready requires the full release corpus")

    if args.write_oracle_fixture and args.strict_oracle:
        parser.error("--write-oracle-fixture cannot be combined with --strict-oracle")

    oracle_fixture = args.oracle_fixture
    if args.strict_oracle and not oracle_fixture:
        oracle_fixture = str(DEFAULT_SMOKE_ORACLE_FIXTURE)

    # Writing a fixture is an ordinary run whose cache is the fixture itself,
    # forced to recompute so every answer comes from the engine at hand.
    cache_path = args.write_oracle_fixture or args.cache_path
    refresh_cache = args.refresh_cache or bool(args.write_oracle_fixture)

    stockfish_path = find_stockfish(args.stockfish)
    # A strict run answers every query from the committed fixture, so it must
    # not require an engine the runner does not have.
    if not stockfish_path and not args.strict_oracle:
        parser.error("Stockfish was not found; pass --stockfish or set STOCKFISH_PATH")
    nodes = args.nodes or (
        DEFAULT_SMOKE_NODES
        if args.profile == PROFILE_SMOKE
        else DEFAULT_RELEASE_NODES
    )
    try:
        feature_weights = parse_feature_weights(args.feature_weight)
    except ValueError as exc:
        parser.error(str(exc))
    try:
        corpus_positions = load_corpus(args.corpus, args.split) if args.corpus else None
        if corpus_positions is not None:
            corpus_positions = limit_positions_per_topic(
                corpus_positions, args.limit_per_topic
            )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    report = run(
        stockfish_path,
        nodes=nodes,
        profile=args.profile,
        topics=args.topic,
        cache_path=cache_path,
        use_cache=not args.no_cache,
        refresh_cache=refresh_cache,
        feature_weights=feature_weights,
        positions=corpus_positions,
        oracle_fixture=oracle_fixture,
        strict_oracle=args.strict_oracle,
    )
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"Teaching accuracy ({report['profile']}, {report['positions']} positions, "
            f"{report['duration_seconds']:.1f}s): "
            f"top3={report['top1_in_oracle_top3_rate']:.0%} "
            f"recall={report['oracle_best_recall_rate']:.0%} "
            f"inversions={report['average_rank_inversion_rate']:.1%}"
        )
        cache_stats = report["oracle_cache"]
        print(
            "  Oracle cache: "
            f"hits={cache_stats['hits']} misses={cache_stats['misses']} "
            f"writes={cache_stats['writes']}"
        )
        for item in report["results"]:
            print(
                f"  {item['name']}: reported={item['reported_top']} "
                f"oracle={item['oracle_best']} top3={item['top_in_oracle_top3']} "
                f"recall={item['oracle_best_recalled']} inversions={item['rank_inversion_rate']:.1%}"
            )
    return 1 if args.require_release_ready and not report["release_ready"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
