import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import axios from "axios";
import App from "./App";

vi.mock("axios", () => ({ default: { get: vi.fn(), post: vi.fn(), isCancel: vi.fn(() => false) } }));
// Expose the props App hands to the board so tests can read styles and click squares.
const board = vi.hoisted(() => ({ props: null }));
vi.mock("react-chessboard", () => ({
  Chessboard: (props) => {
    board.props = props;
    return <div aria-label="棋盤" />;
  }
}));
vi.mock("./EvaluationChart", () => ({ default: () => <div>評分圖</div> }));

beforeEach(() => {
  vi.clearAllMocks();
  const data = new Map();
  vi.stubGlobal("localStorage", { getItem: (key) => data.get(key) || null, setItem: (key, value) => data.set(key, value) });
  HTMLElement.prototype.scrollTo = vi.fn();
  axios.get.mockResolvedValue({ data: [] });
});

describe("board guidance", () => {
  it("shows where a picked-up piece can go in a normal game", () => {
    render(<App />);
    act(() => { board.props.onSquareClick("g1"); });
    expect(Object.keys(board.props.customSquareStyles).sort()).toEqual(["f3", "g1", "h3"]);

    act(() => { board.props.onSquareClick("g1"); });
    expect(board.props.customSquareStyles).toEqual({});

    act(() => { board.props.onPieceDragBegin("wP", "e2"); });
    expect(Object.keys(board.props.customSquareStyles).sort()).toEqual(["e3", "e4"]);
    act(() => { board.props.onPieceDragEnd("wP", "e2"); });
    expect(board.props.customSquareStyles).toEqual({});
  });

  it("does not show moves for the opponent's pieces", () => {
    render(<App />);
    act(() => { board.props.onSquareClick("g8"); });
    expect(board.props.customSquareStyles).toEqual({});
  });

  it("walks lesson hints from text to the piece to an arrow", () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "學習專區" }));
    fireEvent.click(screen.getAllByRole("button", { name: /開始課程|繼續練習/ })[0]);

    const hint = () => screen.getByRole("button", { name: /提示|箭頭/ });
    expect(hint()).toHaveTextContent("給我觀念提示");
    fireEvent.click(hint());
    expect(board.props.customArrows).toEqual([]);
    expect(board.props.customSquareStyles).toEqual({});

    expect(hint()).toHaveTextContent("提示該動哪顆棋");
    fireEvent.click(hint());
    expect(board.props.customSquareStyles.e2.boxShadow).toBeTruthy();
    expect(board.props.customArrows).toEqual([]);

    expect(hint()).toHaveTextContent("顯示走法箭頭");
    fireEvent.click(hint());
    expect(board.props.customArrows.map(([from, to]) => from + to)).toEqual(["e2e4"]);
    expect(hint()).toBeDisabled();
    expect(screen.getByText("提示 3")).toBeInTheDocument();
  });
});
