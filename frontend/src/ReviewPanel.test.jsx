import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import axios from "axios";
import App from "./App";
import { streamReview } from "./reviewStream";
import { ONBOARDING_KEY } from "./onboardingStorage";

vi.mock("axios", () => ({ default: { get: vi.fn(), post: vi.fn(), isCancel: vi.fn(() => false) } }));
vi.mock("./reviewStream", () => ({ streamReview: vi.fn() }));
const board = vi.hoisted(() => ({ props: null }));
vi.mock("react-chessboard", () => ({
  Chessboard: (props) => {
    board.props = props;
    return <div aria-label="棋盤" />;
  }
}));
vi.mock("./EvaluationChart", () => ({ default: ({ labels }) => <div>評分圖 {labels.join(" ")}</div> }));

// 1. e4 e5 2. Qh5?? Nc6? — reviewed rows: start + four moves.
const ROWS = [
  { fen: "start", score: 0, move_number: 0 },
  { fen: "a", score: 30, move_number: 1, side_to_move: "white", move: "e2e4", best_move: "e2e4", classification: "good" },
  { fen: "b", score: 20, move_number: 2, side_to_move: "black", move: "e7e5", best_move: "e7e5", classification: "good" },
  { fen: "c", score: -150, move_number: 3, side_to_move: "white", move: "d1h5", best_move: "g1f3", classification: "blunder", cp_loss: 170 },
  { fen: "d", score: 60, move_number: 4, side_to_move: "black", move: "b8c6", best_move: "g8f6", classification: "mistake", cp_loss: 210 },
];

const position = () => within(screen.getByRole("region", { name: "復盤" })).getByText(/之後|開局/, { selector: "strong" }).textContent;

async function reviewGame() {
  const replies = ["e7e5", "b8c6"];
  axios.post.mockImplementation((url) => Promise.resolve({ data: url.endsWith("/make_move") ? { best_move: replies.shift() } : {} }));
  streamReview.mockResolvedValue({ rows: ROWS, review_id: "r", engine: "Stockfish", quick_nodes: 1, deep_nodes: 1, refined: 0, candidates: 0 });
  render(<App />);
  await act(async () => { board.props.onPieceDrop("e2", "e4"); });
  await waitFor(() => expect(board.props.position).toContain("4p3"));
  await act(async () => { board.props.onPieceDrop("d1", "h5"); });
  await waitFor(() => expect(board.props.position).toContain("n"));
  await waitFor(() => expect(axios.post.mock.calls.filter(([url]) => url.endsWith("/make_move"))).toHaveLength(2));
  fireEvent.click(screen.getByRole("button", { name: "賽後分析" }));
  await screen.findByRole("region", { name: "復盤" });
}

beforeEach(() => {
  vi.clearAllMocks();
  const data = new Map([[ONBOARDING_KEY, JSON.stringify({ level: "player", tipsDismissed: true })]]);
  vi.stubGlobal("localStorage", { getItem: (key) => data.get(key) || null, setItem: (key, value) => data.set(key, value) });
  HTMLElement.prototype.scrollTo = vi.fn();
  axios.get.mockResolvedValue({ data: [] });
});

describe("review panel", () => {
  it("sits under the board with a move list, critical chips and a labelled chart", async () => {
    await reviewGame();
    const panel = screen.getByRole("region", { name: "復盤" });
    const moves = within(within(panel).getByRole("list", { name: "棋譜" })).getAllByRole("button");
    expect(moves.map((move) => move.textContent)).toEqual(["e4", "e5", "Qh5??", "Nc6?"]);
    // The chart is lazy-loaded, so wait for it.
    expect(await within(panel).findByText(/評分圖 開局 1\. e4 1\.\.\. e5 2\. Qh5\?\? 2\.\.\. Nc6\?/)).toBeInTheDocument();
    expect(within(panel).getByRole("button", { name: "大失誤 2. Qh5??" })).toBeInTheDocument();
    expect(within(panel).getByRole("button", { name: "錯誤 2... Nc6?" })).toBeInTheDocument();
    // The side panel no longer hosts the chart.
    expect(document.querySelectorAll("aside .analysis-card")).toHaveLength(0);
  });

  it("steps with buttons, the move list, chips and the keyboard", async () => {
    await reviewGame();
    expect(position()).toBe("2... Nc6? 之後");

    fireEvent.click(screen.getByRole("button", { name: "大失誤 2. Qh5??" }));
    expect(position()).toBe("1... e5 之後");  // before the blunder, where its arrows are drawn
    expect(board.props.customArrows.map(([from, to]) => from + to)).toEqual(["g1f3", "d1h5"]);

    fireEvent.click(screen.getByRole("button", { name: "e4" }));
    expect(position()).toBe("1. e4 之後");
    expect(screen.getByRole("button", { name: "e4" })).toHaveAttribute("aria-current", "step");

    fireEvent.keyDown(window, { key: "ArrowRight" });
    expect(position()).toBe("1... e5 之後");
    fireEvent.keyDown(window, { key: "Home" });
    expect(position()).toBe("開局");
    fireEvent.keyDown(window, { key: "End" });
    expect(position()).toBe("2... Nc6? 之後");

    // Arrow keys while typing to the coach stay in the text box.
    fireEvent.keyDown(screen.getByPlaceholderText(/問教練問題/), { key: "ArrowLeft" });
    expect(position()).toBe("2... Nc6? 之後");

    fireEvent.click(screen.getByRole("button", { name: "上一步" }));
    expect(position()).toBe("2. Qh5?? 之後");
    fireEvent.click(screen.getByRole("button", { name: "回到開頭" }));
    expect(screen.getByRole("button", { name: "上一步" })).toBeDisabled();
  });

  it("stays out of lessons", async () => {
    await reviewGame();
    fireEvent.click(screen.getByRole("button", { name: "學習專區" }));
    fireEvent.click(screen.getAllByRole("button", { name: /開始課程|繼續練習/ })[0]);
    expect(screen.queryByRole("region", { name: "復盤" })).not.toBeInTheDocument();
    fireEvent.keyDown(window, { key: "Home" });
    fireEvent.click(screen.getByRole("button", { name: "對局" }));
    expect(position()).toBe("2... Nc6? 之後");  // the lesson did not move the review
  });
});
