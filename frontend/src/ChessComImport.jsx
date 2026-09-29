import { useEffect, useRef, useState } from "react";
import axios from "axios";
import { loadImports, rememberImport, saveImports, validImport } from "./chesscomStorage";

const API_URL = import.meta.env.VITE_API_URL || "/api";

function gameLabel(game) {
  const opponent = game.perspective === "white" ? game.black : game.white;
  const win = game.result === (game.perspective === "white" ? "1-0" : "0-1");
  const outcome = game.result === "1/2-1/2" ? "和棋" : win ? "勝" : "敗";
  return `${game.username} vs ${opponent} · ${outcome} · 執${game.perspective === "white" ? "白" : "黑"}`;
}

function timeLabel(game) {
  const control = game.time_control || "";
  const daily = /^1\/(\d+)$/.exec(control);
  if (daily) return `每日棋 · 每步 ${Number(daily[1]) / 86400} 天`;
  const live = /^(\d+)(?:\+(\d+))?$/.exec(control);
  if (live) return `${Number(live[1]) / 60} 分鐘${live[2] ? `，每步加 ${live[2]} 秒` : ""}`;
  return "用時未提供";
}

export function ChessComImport({ onImport }) {
  const [username, setUsername] = useState("");
  const [player, setPlayer] = useState("");
  const [months, setMonths] = useState([]);
  const [month, setMonth] = useState("");
  const [page, setPage] = useState(0);
  const [games, setGames] = useState([]);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(loadImports);
  const request = useRef(null);
  useEffect(() => () => request.current?.abort(), []);

  async function fetchGames(name, selectedMonth, selectedPage, controller) {
    const response = await axios.get(`${API_URL}/imports/chesscom/${encodeURIComponent(name)}/${selectedMonth}`, {
      params: { page: selectedPage }, signal: controller.signal,
    });
    if (controller.signal.aborted) return;
    const data = response.data;
    setGames((data.games || []).filter(validImport));
    setHasMore(Boolean(data.has_more));
    setPage(selectedPage);
    setMonth(selectedMonth);
    setNotice(data.skipped ? `略過 ${data.skipped} 局無法分析的棋譜。` : "");
  }

  async function browse(search = false, selectedMonth = month, selectedPage = 0) {
    const name = (search ? username : player).trim().toLowerCase();
    if (!/^[a-z0-9_-]{1,50}$/.test(name)) {
      setError("請輸入 Chess.com 使用者名稱，不是網址。");
      return;
    }
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setLoading(true); setError(""); setNotice(""); setGames([]); setHasMore(false);
    if (search) { setMonths([]); setMonth(""); setPlayer(""); }
    try {
      if (search) {
        const response = await axios.get(`${API_URL}/imports/chesscom/${encodeURIComponent(name)}/archives`, { signal: controller.signal });
        if (controller.signal.aborted) return;
        const available = response.data.months || [];
        setMonths(available); setPlayer(name);
        if (!available.length) { setNotice("這個帳號目前沒有公開的已完成對局。"); return; }
        selectedMonth = available[0];
      }
      await fetchGames(name, selectedMonth, selectedPage, controller);
    } catch (err) {
      if (!controller.signal.aborted) {
        const detail = err.response?.data?.detail;
        setError(typeof detail === "string" ? detail : "讀取失敗，請確認後端連線後重試。");
      }
    } finally {
      if (request.current === controller) { request.current = null; setLoading(false); }
    }
  }

  function open(game) {
    if (!onImport(game)) { setError("這份棋譜無法載入，請選擇其他棋局。"); return; }
    const next = rememberImport(saved, game);
    setSaved(next);
    setError("");
    setNotice(saveImports(next) ? "已匯入並保存在此瀏覽器。接著按「分析這局」。" : "已匯入，但本機儲存空間不可用；重新整理後不會保留。");
  }

  return (
    <section className="import-card" aria-label="Chess.com 棋局匯入">
      <h3>匯入 Chess.com 對局</h3>
      <p className="import-help">免登入查詢公開棋局。最近 10 筆匯入紀錄保存在此瀏覽器，清除網站資料後會消失。</p>
      <form className="import-search" onSubmit={(event) => { event.preventDefault(); browse(true); }}>
        <label htmlFor="chesscom-username">Chess.com 使用者名稱</label>
        <div>
          <input id="chesscom-username" value={username} onChange={(event) => setUsername(event.target.value)} maxLength={50} autoComplete="off" placeholder="例如 erik" />
          <button className="btn btn-primary" disabled={loading || !username.trim()}>{loading ? "讀取中…" : "查詢對局"}</button>
        </div>
      </form>
      {months.length > 0 && (
        <label className="import-month">對局月份（{player}）
          <select value={month} disabled={loading} onChange={(event) => browse(false, event.target.value)} aria-label="對局月份">
            {!month && <option value="">選擇月份</option>}
            {months.map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
        </label>
      )}
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      {month && !loading && !error && !games.length && <p>這頁沒有可分析的標準西洋棋對局。</p>}
      <ul className="import-games" aria-label="可匯入對局">
        {games.map((game) => (
          <li key={game.id}>
            <div><strong>{gameLabel(game)}</strong><small>{new Date(game.end_time * 1000).toLocaleString("zh-TW")} · {timeLabel(game)}</small></div>
            <button className="btn btn-secondary btn-sm" onClick={() => open(game)} aria-label={`匯入 ${gameLabel(game)}`}>匯入此局</button>
          </li>
        ))}
      </ul>
      {month && !error && (page > 0 || hasMore) && <div className="import-pages">
        <button className="btn btn-ghost btn-sm" disabled={loading || page === 0} onClick={() => browse(false, month, page - 1)}>較新對局</button>
        <span>第 {page + 1} 頁</span>
        <button className="btn btn-ghost btn-sm" disabled={loading || !hasMore} onClick={() => browse(false, month, page + 1)}>較舊對局</button>
      </div>}
      {saved.length > 0 && <details className="import-saved">
        <summary>本機匯入紀錄（{saved.length}）</summary>
        <ul>{saved.map((game) => <li key={`${game.id}-${game.perspective}`}><button className="btn btn-ghost btn-sm" onClick={() => open(game)}>開啟 {gameLabel(game)} · {new Date(game.end_time * 1000).toLocaleDateString("zh-TW")}</button></li>)}</ul>
        <button className="btn btn-ghost btn-sm" onClick={() => {
          if (saveImports([])) { setSaved([]); setNotice("已清除本機匯入紀錄。"); }
          else setError("無法清除本機紀錄，請檢查瀏覽器儲存設定。");
        }}>清除本機匯入紀錄</button>
      </details>}
      <p className="import-help">只列出已完成的標準西洋棋；棋譜最多 400 個半回合。Chess.com 的新對局可能延遲出現。</p>
    </section>
  );
}
