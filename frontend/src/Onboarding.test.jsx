import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import axios from "axios";
import App from "./App";
import { ONBOARDING_KEY } from "./onboardingStorage";

vi.mock("axios", () => ({ default: { get: vi.fn(), post: vi.fn(), isCancel: vi.fn(() => false) } }));
vi.mock("react-chessboard", () => ({ Chessboard: () => <div aria-label="棋盤" /> }));
vi.mock("./EvaluationChart", () => ({ default: () => <div>評分圖</div> }));

let store;

beforeEach(() => {
  vi.clearAllMocks();
  store = new Map();
  vi.stubGlobal("localStorage", { getItem: (key) => store.get(key) || null, setItem: (key, value) => store.set(key, value) });
  HTMLElement.prototype.scrollTo = vi.fn();
  axios.get.mockResolvedValue({ data: [] });
});

const dialog = () => screen.queryByRole("dialog", { name: "你目前的程度是？" });
const selectedDifficulty = () => document.querySelector(".bot-settings .option-tile.is-selected")?.textContent;
const coachBeforeImport = () => {
  const coach = document.querySelector(".coach-card");
  const importCard = document.querySelector(".import-card");
  return Boolean(coach.compareDocumentPosition(importCard) & Node.DOCUMENT_POSITION_FOLLOWING);
};

describe("first-visit onboarding", () => {
  it("asks once; a beginner starts the first rules lesson, then plays the easiest bot with tips", () => {
    const { unmount } = render(<App />);
    expect(dialog()).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /我是新手/ }));

    expect(dialog()).not.toBeInTheDocument();
    expect(screen.getAllByText("車、象、后怎麼走").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/把 a1 的車往上走到 a7/).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "對局" }));
    expect(selectedDifficulty()).toContain("新手");
    expect(screen.getByRole("region", { name: "新手提示" })).toBeInTheDocument();
    expect(coachBeforeImport()).toBe(true);
    expect(JSON.parse(store.get(ONBOARDING_KEY))).toEqual({ level: "beginner", tipsDismissed: false });

    unmount();
    render(<App />);
    expect(dialog()).not.toBeInTheDocument();
    expect(selectedDifficulty()).toContain("新手");
  });

  it("recommends rules lessons first to beginners but not to players", () => {
    store.set(ONBOARDING_KEY, JSON.stringify({ level: "beginner", tipsDismissed: true }));
    const { unmount } = render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "學習專區" }));
    const plan = () => [...document.querySelectorAll(".lesson-card h4")].map((node) => node.textContent);
    expect(plan()[0]).toBe("車、象、后怎麼走");
    expect(screen.getAllByText("新手先學會棋子怎麼走").length).toBeGreaterThan(0);
    unmount();

    store.set(ONBOARDING_KEY, JSON.stringify({ level: "player", tipsDismissed: false }));
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "學習專區" }));
    expect(plan().some((title) => title.includes("怎麼走") || title.includes("將死與逼和"))).toBe(false);
    expect(screen.getByText("王與將軍")).toBeInTheDocument(); // still listed in the curriculum map
  });

  it("remembers when the beginner tips are dismissed", () => {
    store.set(ONBOARDING_KEY, JSON.stringify({ level: "beginner", tipsDismissed: false }));
    const { unmount } = render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "知道了" }));
    expect(screen.queryByRole("region", { name: "新手提示" })).not.toBeInTheDocument();
    unmount();
    render(<App />);
    expect(screen.queryByRole("region", { name: "新手提示" })).not.toBeInTheDocument();
  });

  it("a player keeps the intermediate bot and sees no tips", () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: /我會下棋/ }));
    expect(selectedDifficulty()).toContain("中階");
    expect(screen.queryByRole("region", { name: "新手提示" })).not.toBeInTheDocument();
    expect(coachBeforeImport()).toBe(true);
  });

  it("a Chess.com player gets the import card first with the username box focused", async () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: /我在 Chess.com 下棋/ }));
    expect(coachBeforeImport()).toBe(false);
    await waitFor(() => expect(screen.getByLabelText("Chess.com 使用者名稱")).toHaveFocus());
  });

  it("can be reopened from the bot settings or closed without changing anything", () => {
    store.set(ONBOARDING_KEY, JSON.stringify({ level: "player", tipsDismissed: false }));
    render(<App />);
    expect(dialog()).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "重新選擇程度" }));
    expect(dialog()).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "先不用，維持目前設定" }));
    expect(dialog()).not.toBeInTheDocument();
    expect(selectedDifficulty()).toContain("中階");
  });

  it("still works when the browser refuses storage", () => {
    vi.stubGlobal("localStorage", {
      getItem: () => { throw new Error("blocked"); },
      setItem: () => { throw new Error("blocked"); },
    });
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: /我是新手/ }));
    expect(dialog()).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "對局" }));
    expect(selectedDifficulty()).toContain("新手");
  });
});
