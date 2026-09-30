import { CLASSIFICATION_LABELS, criticalMoves, movePairs } from "./reviewMoves";

function MoveButton({ move, selectedIndex, onSelect }) {
  if (!move) return <span className="move-list__empty" />;
  return (
    <button
      className={`move-list__move ${move.index === selectedIndex ? "is-current" : ""} ${move.classification ? `is-${move.classification}` : ""}`}
      aria-current={move.index === selectedIndex ? "step" : undefined}
      onClick={() => onSelect(move.index)}
    >
      {move.san}{move.mark}
    </button>
  );
}

/**
 * Review controls that sit under the board, so the board stays in view while
 * stepping, scrubbing the chart or picking a move.
 */
export function ReviewPanel({ moves, selectedIndex, onSelect, chart }) {
  const last = moves.length;
  const current = selectedIndex > 0 ? moves[selectedIndex - 1] : null;
  const next = moves[selectedIndex] || null;
  const critical = criticalMoves(moves);

  return (
    <section className="review-panel" aria-label="復盤">
      <div className="review-panel__nav">
        <button className="btn btn-ghost btn-sm" aria-label="回到開頭" disabled={selectedIndex === 0} onClick={() => onSelect(0)}>⏮</button>
        <button className="btn btn-ghost btn-sm" disabled={selectedIndex === 0} onClick={() => onSelect(selectedIndex - 1)}>上一步</button>
        <div className="review-panel__position" aria-live="polite">
          <strong>{current ? `${current.label}${current.mark} 之後` : "開局"}</strong>
          <small>
            {next
              ? `下一步：${next.label}${next.mark}${next.classification && CLASSIFICATION_LABELS[next.classification] ? `（${CLASSIFICATION_LABELS[next.classification]}）` : ""}`
              : "棋局結束"}
          </small>
        </div>
        <button className="btn btn-ghost btn-sm" disabled={selectedIndex >= last} onClick={() => onSelect(selectedIndex + 1)}>下一步</button>
        <button className="btn btn-ghost btn-sm" aria-label="跳到結尾" disabled={selectedIndex >= last} onClick={() => onSelect(last)}>⏭</button>
      </div>

      {critical.length > 0 && (
        <div className="review-panel__critical">
          <span>關鍵失誤：</span>
          {critical.map((move) => (
            <button
              key={move.index}
              className={`review-chip is-${move.classification}`}
              title="跳到這步之前，看推薦手和實際走法"
              // The position before the mistake is where its arrows (recommended vs played) are drawn.
              onClick={() => onSelect(move.index - 1)}
            >
              {CLASSIFICATION_LABELS[move.classification]} {move.label}{move.mark}
            </button>
          ))}
        </div>
      )}

      {chart}

      <ol className="move-list" aria-label="棋譜">
        {movePairs(moves).map((pair) => (
          <li key={`${pair.number}-${pair.white?.index ?? pair.black?.index}`}>
            <span className="move-list__number">{pair.number}.</span>
            <MoveButton move={pair.white} selectedIndex={selectedIndex} onSelect={onSelect} />
            <MoveButton move={pair.black} selectedIndex={selectedIndex} onSelect={onSelect} />
          </li>
        ))}
      </ol>
      <p className="review-panel__hint">點圖表、棋譜或關鍵失誤可以跳到那一步；也可以用 ← → 鍵，Home／End 到開頭或結尾。</p>
    </section>
  );
}
