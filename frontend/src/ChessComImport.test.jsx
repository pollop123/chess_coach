import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Chess } from "chess.js";
import axios from "axios";
import App from "./App";
import { streamReview } from "./reviewStream";
vi.mock("./reviewStream", () => ({ streamReview: vi.fn() }));
import { ChessComImport } from "./ChessComImport";
import { IMPORTS_KEY, loadImports, rememberImport, saveImports } from "./chesscomStorage";

vi.mock("axios", () => ({ default: { get: vi.fn(), post: vi.fn(), isCancel: vi.fn(() => false) } }));
vi.mock("react-chessboard", () => ({ Chessboard: ({ onPieceDrop, boardOrientation }) => <button aria-label={`棋盤 ${boardOrientation}`} onClick={() => onPieceDrop("e2", "e4")} /> }));
vi.mock("./EvaluationChart", () => ({ default: () => <div>評分圖</div> }));
const pgn = '[White "Opponent"]\n[Black "Player"]\n[Result "0-1"]\n\n1. f3 e5 2. g4 Qh4# 0-1';
const imported = { id: "https://www.chess.com/game/live/123", url: "https://www.chess.com/game/live/123", username: "player", white: "Opponent", black: "Player", perspective: "black", result: "0-1", end_time: 1700000000, pgn, time_class: "rapid", time_control: "600" };

beforeEach(() => {
  vi.clearAllMocks();
  const data = new Map();
  vi.stubGlobal("localStorage", { getItem: (key) => data.get(key) || null, setItem: (key, value) => data.set(key, value) });
  HTMLElement.prototype.scrollTo = vi.fn();
  axios.get.mockImplementation((url) => Promise.resolve({ data: url.endsWith("archives") ? { months: ["2025/02", "2025/01"] } : url.includes("chesscom") ? { games: [imported], has_more: false } : [] }));
});
afterEach(() => vi.unstubAllGlobals());

async function searchAndImport() {
  fireEvent.change(screen.getByLabelText("Chess.com 使用者名稱"), { target: { value: "Player" } });
  fireEvent.click(screen.getByRole("button", { name: "查詢對局" }));
  fireEvent.click(await screen.findByRole("button", { name: /匯入 player vs Opponent/ }));
}

describe("Chess.com import", () => {
  it("imports, detects the player's side, reviews and asks the coach before a move", async () => {
    const board = new Chess();
    const rows = [{ fen: board.fen(), score: 0 }];
    board.move("f3"); rows.push({ fen: board.fen(), score: -50, side_to_move: "white", cp_loss: 50 });
    board.move("e5"); rows.push({ fen: board.fen(), score: -30, side_to_move: "black", cp_loss: 20 });
    streamReview.mockResolvedValue({ rows, review_id: "stored-evidence", engine: "Stockfish", quick_nodes: 50000, deep_nodes: 500000, refined: 1, candidates: 1 });
    axios.post.mockResolvedValue({ data: { advice: "先檢查中心與王的安全。", sources: [], mode: "position" } });
    render(<App />);
    await searchAndImport();
    expect(screen.getByRole("button", { name: "棋盤 black" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "投降" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "棋盤 black" }));
    expect(axios.post).not.toHaveBeenCalled();
    expect(loadImports()).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "分析這局" }));
    fireEvent.click(await screen.findByRole("button", { name: "請教練講解這個局面" }));
    await screen.findByText("先檢查中心與王的安全。");
    const analysis = streamReview.mock.calls[0];
    expect(analysis[1].perspective).toBe("black");
    expect(analysis[1].pgn).toContain("Qh4#");
    const coach = axios.post.mock.calls.find(([url]) => url.endsWith("explain"));
    expect(coach[1].fen).toBe(rows[1].fen);
    expect(coach[1].review_id).toBe("stored-evidence");
    expect(coach[1].review_ply).toBe(1);
    expect(axios.post.mock.calls.some(([url]) => url.endsWith("/games"))).toBe(false);
  });

  it("deduplicates local imports and reopens them without an API request", async () => {
    const onImport = vi.fn(() => true);
    const { unmount } = render(<ChessComImport onImport={onImport} />);
    await searchAndImport();
    fireEvent.click(screen.getByRole("button", { name: /匯入 player vs Opponent/ }));
    expect(loadImports()).toHaveLength(1);
    unmount(); axios.get.mockClear();
    render(<ChessComImport onImport={onImport} />);
    fireEvent.click(screen.getByText("本機匯入紀錄（1）"));
    fireEvent.click(screen.getByRole("button", { name: /開啟 player vs Opponent/ }));
    expect(axios.get).not.toHaveBeenCalled();
    expect(onImport).toHaveBeenLastCalledWith(imported);
    fireEvent.click(screen.getByRole("button", { name: "清除本機匯入紀錄" }));
    expect(loadImports()).toEqual([]);
  });

  it("handles provider errors and unavailable local storage", async () => {
    axios.get.mockRejectedValueOnce({ response: { data: { detail: "Chess.com 暫時限制請求" } } });
    render(<ChessComImport onImport={() => true} />);
    fireEvent.change(screen.getByLabelText("Chess.com 使用者名稱"), { target: { value: "Player" } });
    fireEvent.click(screen.getByRole("button", { name: "查詢對局" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("暫時限制請求");
    window.localStorage.setItem = () => { throw new Error("quota"); };
    await searchAndImport();
    expect(screen.getByRole("status")).toHaveTextContent("本機儲存空間不可用");
  });

  it("does not apply an old analysis after another game is imported", async () => {
    let resolve;
    streamReview.mockImplementation(() => new Promise((done) => { resolve = done; }));
    render(<App />);
    await searchAndImport();
    fireEvent.click(screen.getByRole("button", { name: "分析這局" }));
    const signal = streamReview.mock.calls[0][2];
    fireEvent.click(screen.getByRole("button", { name: /匯入 player vs Opponent/ }));
    expect(signal.aborted).toBe(true);
    await act(async () => resolve({ rows: [{ fen: new Chess().fen(), score: 99 }], review_id: "stale" }));
    expect(screen.queryByRole("button", { name: "請教練講解這個局面" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "分析這局" })).toBeEnabled();
  });

  it("handles malformed saved records and bounds history", () => {
    window.localStorage.setItem(IMPORTS_KEY, "invalid");
    expect(loadImports()).toEqual([]);
    const many = Array.from({ length: 15 }, (_, index) => ({ ...imported, id: `https://www.chess.com/game/live/${index}` }));
    expect(rememberImport(many, imported)).toHaveLength(10);
    expect(saveImports([...many, { pgn: "broken" }])).toBe(true);
    expect(loadImports()).toHaveLength(10);
  });

  it("shows both phases and cancels without exposing provisional coaching", async () => {
    let finish;
    streamReview.mockImplementation(() => new Promise((resolve) => { finish = resolve; }));
    render(<App />);
    await searchAndImport();
    fireEvent.click(screen.getByRole("button", { name: "分析這局" }));
    const [, , signal, progress] = streamReview.mock.calls[0];
    expect(screen.getByText("全局初評：0 / 4")).toBeInTheDocument();
    act(() => progress({ phase: "deep", current: 1, total: 2 }));
    expect(screen.getByText("加深複核關鍵步：1 / 2")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("問教練問題 (例如：為什麼這步不好？)")).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "取消分析" }));
    expect(signal.aborted).toBe(true);
    await act(async () => finish({ rows: [], review_id: "cancelled" }));
    expect(screen.queryByRole("button", { name: "請教練講解這個局面" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "分析這局" })).toBeEnabled();
  });
});
