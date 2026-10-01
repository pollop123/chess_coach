// Finished games stay in this browser only; nothing is shared with other users.
export const GAMES_KEY = "chess-coach.games.v1";
export const MAX_GAMES = 30;
const RESULTS = new Set(["1-0", "0-1", "1/2-1/2"]);

export function validGame(game) {
  return Boolean(game) && typeof game.id === "string" && game.id.length <= 64
    && typeof game.pgn === "string" && game.pgn.length > 0 && game.pgn.length <= 200000
    && RESULTS.has(game.result)
    && typeof game.date === "string" && !Number.isNaN(Date.parse(game.date))
    && (game.playerColor === undefined || game.playerColor === "white" || game.playerColor === "black");
}

export function loadGames() {
  try {
    const data = JSON.parse(window.localStorage.getItem(GAMES_KEY) || "[]");
    return Array.isArray(data) ? data.filter(validGame).slice(0, MAX_GAMES) : [];
  } catch {
    return [];
  }
}

export function saveGames(games) {
  try {
    window.localStorage.setItem(GAMES_KEY, JSON.stringify(games.filter(validGame).slice(0, MAX_GAMES)));
    return true;
  } catch {
    return false;
  }
}

export function addGame(games, game) {
  return [game, ...games.filter((item) => item.id !== game.id)].slice(0, MAX_GAMES);
}

/** 勝／負／和 from the player's side; games saved before colours were recorded fall back to White. */
export function outcomeForPlayer(game) {
  if (game.result === "1/2-1/2") return "draw";
  const whiteWon = game.result === "1-0";
  return (game.playerColor === "black") === whiteWon ? "loss" : "win";
}
