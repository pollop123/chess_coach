import { afterEach, describe, expect, it, vi } from "vitest";
import { GAMES_KEY, MAX_GAMES, addGame, loadGames, outcomeForPlayer, saveGames } from "./gameHistoryStorage";

const game = (id, extra = {}) => ({ id, pgn: "1. e4 e5", result: "1-0", date: "2026-10-01T00:00:00Z", playerColor: "white", ...extra });

function stubStorage(store = new Map()) {
  vi.stubGlobal("localStorage", { getItem: (key) => store.get(key) || null, setItem: (key, value) => store.set(key, value) });
  return store;
}

afterEach(() => vi.unstubAllGlobals());

describe("game history storage", () => {
  it("keeps the newest 30 games and replaces a repeated id", () => {
    let games = [];
    for (let i = 0; i < MAX_GAMES + 5; i += 1) games = addGame(games, game(`g${i}`));
    expect(games).toHaveLength(MAX_GAMES);
    expect(games[0].id).toBe(`g${MAX_GAMES + 4}`);
    expect(addGame(games, game(games[5].id, { result: "0-1" }))[0].result).toBe("0-1");
  });

  it("round-trips through storage and drops malformed entries", () => {
    const store = stubStorage();
    expect(saveGames([game("a"), { id: "bad" }])).toBe(true);
    store.set(GAMES_KEY, JSON.stringify([game("a"), { id: "x", pgn: "", result: "1-0", date: "nope" }, game("b", { result: "2-0" })]));
    expect(loadGames().map((item) => item.id)).toEqual(["a"]);
  });

  it("survives a browser that refuses storage", () => {
    vi.stubGlobal("localStorage", {
      getItem: () => { throw new Error("blocked"); },
      setItem: () => { throw new Error("blocked"); },
    });
    expect(loadGames()).toEqual([]);
    expect(saveGames([game("a")])).toBe(false);
  });

  it("reports 勝／負／和 from the player's side", () => {
    expect(outcomeForPlayer(game("w", { result: "1-0", playerColor: "white" }))).toBe("win");
    expect(outcomeForPlayer(game("b", { result: "1-0", playerColor: "black" }))).toBe("loss");
    expect(outcomeForPlayer(game("b2", { result: "0-1", playerColor: "black" }))).toBe("win");
    expect(outcomeForPlayer(game("d", { result: "1/2-1/2" }))).toBe("draw");
  });
});
