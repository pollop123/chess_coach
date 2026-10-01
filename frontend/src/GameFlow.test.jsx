import { StrictMode } from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import axios from "axios";
import App from "./App";
import { streamReview } from "./reviewStream";
import { GAMES_KEY } from "./gameHistoryStorage";

vi.mock("axios", () => ({ default: { get: vi.fn(), post: vi.fn(), isCancel: vi.fn(() => false) } }));
vi.mock("./reviewStream", () => ({ streamReview: vi.fn() }));
const board = vi.hoisted(() => ({ props: null }));
vi.mock("react-chessboard", () => ({
  Chessboard: (props) => {
    board.props = props;
    return <div aria-label="棋盤" />;
  }
}));
vi.mock("./EvaluationChart", () => ({ default: () => <div>評分圖</div> }));

const FINISHED_PGN = '[Result "0-1"]\n\n1. f3 e5 2. g4 Qh4# 0-1';

function botReplies(...moves) {
  const queue = [...moves];
  axios.post.mockImplementation((url) => {
    if (url.endsWith("/make_move")) return Promise.resolve({ data: { best_move: queue.shift() } });
    return Promise.resolve({ data: {} });
  });
}

let store;
// Finished games now live in this browser's storage, never on the shared server.
const savedGames = () => JSON.parse(store.get(GAMES_KEY) || "[]");

async function play(from, to) {
  await act(async () => { board.props.onPieceDrop(from, to); });
}

beforeEach(() => {
  vi.clearAllMocks();
  store = new Map();
  vi.stubGlobal("localStorage", { getItem: (key) => store.get(key) || null, setItem: (key, value) => store.set(key, value) });
  HTMLElement.prototype.scrollTo = vi.fn();
  axios.get.mockResolvedValue({ data: [] });
});

describe("finishing a game", () => {
  it("saves once, with the bot's mating move, even under StrictMode", async () => {
    botReplies("e7e5", "d8h4");
    render(<StrictMode><App /></StrictMode>);
    await play("f2", "f3");
    await waitFor(() => expect(board.props.position).toContain("4p3"));
    await play("g2", "g4");
    await waitFor(() => expect(savedGames()).toHaveLength(1));
    expect(savedGames()[0].pgn).toContain("Qh4#");
    expect(savedGames()[0].result).toBe("0-1");
    expect(savedGames()[0].playerColor).toBe("white");
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(savedGames()).toHaveLength(1);
    expect(axios.post.mock.calls.some(([url]) => url.endsWith("/games"))).toBe(false);
    // Shown from the player's side: White was mated, so 負.
    expect(screen.getByText("負")).toBeInTheDocument();
  });

  it("saves once, with the player's own mating move", async () => {
    botReplies("e7e5", "b8c6", "g8f6");
    render(<StrictMode><App /></StrictMode>);
    await play("e2", "e4");
    await waitFor(() => expect(axios.post).toHaveBeenCalledTimes(1));
    await play("f1", "c4");
    await waitFor(() => expect(axios.post).toHaveBeenCalledTimes(2));
    await play("d1", "h5");
    await waitFor(() => expect(axios.post).toHaveBeenCalledTimes(3));
    await play("h5", "f7");
    await waitFor(() => expect(savedGames()).toHaveLength(1));
    expect(savedGames()[0].pgn).toContain("Qxf7#");
    expect(savedGames()[0].result).toBe("1-0");
    expect(screen.getByText("勝")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "清除紀錄" }));
    expect(savedGames()).toHaveLength(0);
    expect(screen.getByText(/尚無紀錄/)).toBeInTheDocument();
  });

  it("does not save again when an old finished game is opened", async () => {
    store.set(GAMES_KEY, JSON.stringify([{ id: "g7", pgn: FINISHED_PGN, result: "0-1", date: "2026-01-01T00:00:00Z", playerColor: "black" }]));
    render(<StrictMode><App /></StrictMode>);
    expect(screen.getByText("勝")).toBeInTheDocument();  // Black won the saved game
    fireEvent.click(screen.getByText("你執黑"));
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(savedGames()).toHaveLength(1);
  });
});

describe("post-game review", () => {
  it("replaces the 'analysing' coach message once the review is ready", async () => {
    streamReview.mockResolvedValue({
      rows: [{ fen: "start", score: 0 }, { fen: "after", score: 30, move: "e2e4", best_move: "e2e4" }],
      review_id: "r", engine: "Stockfish", quick_nodes: 1, deep_nodes: 1, refined: 0, candidates: 0,
    });
    botReplies("e7e5");
    render(<App />);
    await play("e2", "e4");
    await waitFor(() => expect(board.props.position).toContain("4p3"));
    fireEvent.click(screen.getByRole("button", { name: "賽後分析" }));
    expect(await screen.findByText(/分析完成了/)).toBeInTheDocument();
    expect(screen.queryByText(/正在整理賽後分析依據/)).not.toBeInTheDocument();
  });
});
