import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Chess } from "chess.js";
import axios from "axios";
import App from "./App";
import { buildLessonChallenges } from "./lessonEngine";
import { ONBOARDING_KEY } from "./onboardingStorage";
import { TRAINING_LESSONS } from "./trainingLessons";

vi.mock("axios", () => ({ default: { get: vi.fn(), post: vi.fn(), isCancel: vi.fn(() => false) } }));
const board = vi.hoisted(() => ({ props: null }));
vi.mock("react-chessboard", () => ({
  Chessboard: (props) => {
    board.props = props;
    return <div aria-label="棋盤" />;
  }
}));
vi.mock("./EvaluationChart", () => ({ default: () => <div>評分圖</div> }));

const RULES_LESSONS = TRAINING_LESSONS.filter((lesson) => lesson.phase === "basics");

beforeEach(() => {
  vi.clearAllMocks();
  const data = new Map([[ONBOARDING_KEY, JSON.stringify({ level: "beginner", tipsDismissed: true })]]);
  vi.stubGlobal("localStorage", { getItem: (key) => data.get(key) || null, setItem: (key, value) => data.set(key, value) });
  HTMLElement.prototype.scrollTo = vi.fn();
  axios.get.mockResolvedValue({ data: [] });
});

describe("rules lessons", () => {
  it("are the six basics lessons, first in the catalog, and never recommended from a review", () => {
    expect(RULES_LESSONS.map((lesson) => lesson.id)).toEqual([
      "rules-rook-bishop-queen", "rules-knight", "rules-pawn", "rules-check", "rules-mate-stalemate", "rules-special-moves",
    ]);
    expect(TRAINING_LESSONS.slice(0, 6)).toEqual(RULES_LESSONS);
    expect(RULES_LESSONS.every((lesson) => lesson.type === "rules" && !lesson.recommendationVerified)).toBe(true);
  });

  it.each(RULES_LESSONS.map((lesson) => [lesson.variation, lesson]))("%s can be played to a full-score pass", (_title, lesson) => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "學習專區" }));
    fireEvent.click(screen.getByRole("button", { name: new RegExp(lesson.variation) }));

    const challenges = buildLessonChallenges(lesson);
    challenges.forEach((challenge, index) => {
      // Every step has its own prompt and a first hint that does not name the answer.
      expect(challenge.prompt).not.toMatch(/^找出局面的最佳手|^運用本課觀念/);
      const move = new Chess(challenge.fen).move(challenge.mainlineMove);
      act(() => { board.props.onPieceDrop(move.from, move.to); });
      expect(screen.getByText(/好棋/)).toBeInTheDocument();
      if (index < challenges.length - 1) fireEvent.click(screen.getByRole("button", { name: "下一個挑戰" }));
    });

    expect(screen.getByRole("region", { name: "課程結業成績" })).toHaveTextContent("100");
  });

  it("marks the stalemating queen move as a mistake, not a pass", () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "學習專區" }));
    fireEvent.click(screen.getByRole("button", { name: /將死與逼和/ }));
    act(() => { board.props.onPieceDrop("g1", "g6"); });  // Qg6 would be stalemate
    expect(screen.queryByText(/好棋/)).not.toBeInTheDocument();
    expect(screen.getByText("錯誤 1")).toBeInTheDocument();
  });
});
