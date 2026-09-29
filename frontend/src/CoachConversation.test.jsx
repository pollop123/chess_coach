import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import axios from "axios";
import { Chess } from "chess.js";
import App from "./App";
import { CoachMessage } from "./CoachMessage";
import { buildCoachConversation } from "./coachConversation";

vi.mock("axios", () => ({ default: { get: vi.fn(), post: vi.fn(), isCancel: vi.fn(() => false) } }));
vi.mock("react-chessboard", () => ({ Chessboard: ({ onPieceDrop }) => <button aria-label="棋盤：走 e4" onClick={() => onPieceDrop("e2", "e4")} /> }));

const fen = new Chess().fen();
const sources = [{ id: "K15", title: "中心控制", text: "控制中心可增加活動空間。", kind: "knowledge" }];

beforeEach(() => {
  vi.clearAllMocks();
  axios.get.mockResolvedValue({ data: [] });
  HTMLElement.prototype.scrollTo = vi.fn();
});

describe("coach conversation", () => {
  it("keeps citations collapsed until the user asks to view evidence", async () => {
    const user = userEvent.setup();
    const { container } = render(<CoachMessage message={{ role: "model", text: "先爭取活動空間。 [K15]", sources }} />);
    expect(screen.getByText("先爭取活動空間。 [K15]")).toBeVisible();
    expect(container.querySelector("details")).not.toHaveAttribute("open");
    await user.click(screen.getByText("查看依據（1）"));
    expect(container.querySelector("details")).toHaveAttribute("open");
    expect(screen.getByText(sources[0].text)).toBeVisible();
  });

  it("bounds context and excludes welcome, errors and other positions", () => {
    const current = { role: "user", text: "中心？", fen };
    const other = new Chess(); other.move("e4");
    const messages = [{ role: "model", text: "歡迎" }, ...Array(10).fill(current), { ...current, error: true }, { ...current, fen: other.fen() }];
    const result = buildCoachConversation(messages, fen);
    expect(result).toHaveLength(8);
    expect(result.every((turn) => turn.fen === fen && turn.text === "中心？")).toBe(true);
  });

  it("sends previous turns with followups and uses overview only for the analysis button", async () => {
    const user = userEvent.setup();
    axios.post.mockResolvedValue({ data: { advice: "中心讓棋子有更多空間。 [K15]", sources, mode: "knowledge", status: "generated" } });
    render(<App />);
    const input = screen.getByPlaceholderText(/問教練問題/);
    await user.type(input, "為什麼要控制中心？");
    await user.click(screen.getByRole("button", { name: "送出問題" }));
    await screen.findByText("中心讓棋子有更多空間。 [K15]");
    expect(axios.post.mock.calls[0][1].conversation).toEqual([]);
    await user.type(input, "再講簡單一點");
    await user.click(screen.getByRole("button", { name: "送出問題" }));
    await waitFor(() => expect(axios.post).toHaveBeenCalledTimes(2));
    const payload = axios.post.mock.calls[1][1];
    expect(payload.mode).toBe("auto");
    expect(payload.player_color).toBe("white");
    expect(payload.conversation.map((turn) => turn.role)).toEqual(["user", "model"]);
    expect(payload.conversation[1].mode).toBe("knowledge");
    await waitFor(() => expect(input).toBeEnabled());
    await user.click(screen.getByRole("button", { name: "分析目前局面" }));
    expect(axios.post.mock.calls[2][1].mode).toBe("overview");
  });

  it("discards a pending answer when a new game starts even at the same FEN", async () => {
    let resolve;
    axios.post.mockImplementation(() => new Promise((done) => { resolve = done; }));
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "分析目前局面" }));
    const signal = axios.post.mock.calls[0][2].signal;
    fireEvent.click(screen.getByRole("button", { name: "新局" }));
    expect(signal.aborted).toBe(true);
    resolve({ data: { advice: "這是前一局的回答", sources } });
    await waitFor(() => expect(screen.getByRole("button", { name: "分析目前局面" })).toBeEnabled());
    expect(screen.queryByText("這是前一局的回答")).not.toBeInTheDocument();
  });

  it("cancels stale answers when the displayed position changes", async () => {
    let resolve;
    axios.post.mockImplementation((url) => url.endsWith("/explain")
      ? new Promise((done) => { resolve = done; }) : new Promise(() => {}));
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "分析目前局面" }));
    const signal = axios.post.mock.calls[0][2].signal;
    fireEvent.click(screen.getByRole("button", { name: "棋盤：走 e4" }));
    expect(signal.aborted).toBe(true);
    resolve({ data: { advice: "這是上一個盤面的回答", sources } });
    await waitFor(() => expect(screen.getByRole("button", { name: "分析目前局面" })).toBeEnabled());
    expect(screen.queryByText("這是上一個盤面的回答")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "分析目前局面" }));
    const coachCalls = axios.post.mock.calls.filter(([url]) => url.endsWith("/explain"));
    expect(coachCalls[1][1].conversation).toEqual([]);
  });
});
