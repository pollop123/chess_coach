export const IMPORTS_KEY = "chess-coach.chesscom-imports.v1";
export const MAX_IMPORTS = 10;

export function validImport(game) {
  return game && typeof game.id === "string" && /^https:\/\/www\.chess\.com\/(game\/(live|daily)|live\/game|daily\/game)\/\d+$/.test(game.id)
    && typeof game.pgn === "string" && game.pgn.length > 0 && game.pgn.length <= 200000
    && ["white", "black"].includes(game.perspective)
    && [game.white, game.black, game.username].every((value) => typeof value === "string" && value.length <= 100)
    && ["1-0", "0-1", "1/2-1/2"].includes(game.result) && Number.isFinite(game.end_time);
}

export function loadImports() {
  try {
    const data = JSON.parse(window.localStorage.getItem(IMPORTS_KEY) || "[]");
    return Array.isArray(data) ? data.filter(validImport).slice(0, MAX_IMPORTS) : [];
  } catch { return []; }
}

export function saveImports(games) {
  try {
    window.localStorage.setItem(IMPORTS_KEY, JSON.stringify(games.filter(validImport).slice(0, MAX_IMPORTS)));
    return true;
  } catch { return false; }
}

export function rememberImport(games, game) {
  return [game, ...games.filter((item) => item.id !== game.id || item.perspective !== game.perspective)].slice(0, MAX_IMPORTS);
}
