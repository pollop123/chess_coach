import {
  Area,
  ComposedChart,
  Line,
  ReferenceArea,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

const TREND_LIMIT = 340;

function getTrendScore(point) {
  const score = point?.rawScore ?? point?.displayScore ?? 0;
  const isMate = point?.is_checkmate || point?.mate_threat || Math.abs(score) > 15000;
  if (isMate) return score >= 0 ? 310 : -310;
  if (score === 0) return 0;
  return Math.sign(score) * Math.min(280, 85 * Math.log1p(Math.abs(score) / 80));
}

function getMoveDotColor(classification) {
  if (classification === "blunder") return "#c93f3a";
  if (classification === "mistake") return "#d9822b";
  return null;
}

function EvalDot({ cx, cy, payload }) {
  const color = getMoveDotColor(payload?.classification);
  if (!payload?.move || !color) return null;
  return (
    <circle
      cx={cx}
      cy={cy}
      r={payload.classification === "blunder" ? 6.5 : 5}
      fill={color}
      stroke="#ffffff"
      strokeWidth={2}
    />
  );
}

function EvalTooltip({ active, payload, label }) {
  if (!active || !payload || payload.length === 0) return null;
  const point = payload[0].payload;
  const classificationLabels = {
    blunder: "大失誤",
    mistake: "錯誤",
    inaccuracy: "稍不精確",
    good: "穩定"
  };
  const sideLabel = point.side_to_move === "black" ? "黑方走" : point.side_to_move === "white" ? "白方走" : "起始局面";
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip__label">第 {label} 步 · {sideLabel}</div>
      <div className="chart-tooltip__value">{point.evalLabel}</div>
      {point.classification && (
        <div className={`chart-tooltip__judgement is-${point.classification}`}>
          {classificationLabels[point.classification] || point.classification}
          {point.cp_loss > 0 ? ` · 損失約 ${(point.cp_loss / 100).toFixed(1)} 兵` : ""}
        </div>
      )}
    </div>
  );
}

export default function EvaluationChart({ analysisData, currentMoveIndex, onMoveSelect }) {
  const chartData = analysisData.map((point) => {
    const trendScore = getTrendScore(point);
    const isCritical = point.move && ["mistake", "blunder"].includes(point.classification);
    return {
      ...point,
      trendScore,
      criticalScore: isCritical ? trendScore : null
    };
  });
  const criticalPoints = chartData.filter((point) =>
    point.move && ["mistake", "blunder"].includes(point.classification)
  );
  const blunderCount = criticalPoints.filter((point) => point.classification === "blunder").length;
  const selectedPoint = currentMoveIndex !== -1 ? chartData[currentMoveIndex] : null;

  return (
    <div className="analysis-card">
      <div className="chart-header">
        <div className="chart-title">
          <strong>局勢走勢</strong>
          <span>白優 ↑ · 黑優 ↓</span>
        </div>
        <div className="chart-summary">
          {criticalPoints.length === 0
            ? "走勢穩定"
            : `${criticalPoints.length} 個關鍵轉折${blunderCount ? ` · ${blunderCount} 個大失誤` : ""}`}
        </div>
      </div>
      <ResponsiveContainer width="100%" height={154}>
        <ComposedChart
          data={chartData}
          margin={{ top: 10, right: 12, bottom: 8, left: 12 }}
          onClick={(event) => {
            if (event?.activePayload) onMoveSelect(event.activePayload[0].payload.move_number);
          }}
        >
          <defs>
            <linearGradient id="evaluationTrendArea" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#2f7455" stopOpacity={0.28}/>
              <stop offset="50%" stopColor="#2f7455" stopOpacity={0.08}/>
              <stop offset="100%" stopColor="#2f7455" stopOpacity={0.2}/>
            </linearGradient>
          </defs>
          <XAxis dataKey="move_number" hide />
          <YAxis hide domain={[-TREND_LIMIT, TREND_LIMIT]} />
          <Tooltip
            cursor={{ stroke: "#8f8a83", strokeWidth: 1 }}
            content={EvalTooltip}
          />
          <ReferenceArea y1={0} y2={TREND_LIMIT} fill="#fbfcfa" fillOpacity={1} />
          <ReferenceArea y1={-TREND_LIMIT} y2={0} fill="#e7ebe7" fillOpacity={1} />
          <ReferenceLine y={0} stroke="#9da69f" strokeDasharray="4 4" strokeWidth={1.5} />
          <Area
            type="linear"
            dataKey="trendScore"
            baseValue={0}
            stroke="none"
            fill="url(#evaluationTrendArea)"
            isAnimationActive={false}
          />
          <Line
            type="linear"
            dataKey="trendScore"
            stroke="#245c45"
            dot={false}
            strokeWidth={3}
            isAnimationActive={false}
            activeDot={{ r: 5, fill: "#ffffff", stroke: "#245c45", strokeWidth: 2 }}
          />
          <Line
            type="linear"
            dataKey="criticalScore"
            stroke="none"
            dot={EvalDot}
            activeDot={false}
            connectNulls={false}
            isAnimationActive={false}
          />
          {selectedPoint && (
            <ReferenceDot
              x={selectedPoint.move_number}
              y={selectedPoint.trendScore}
              r={9}
              fill="transparent"
              stroke="#17231f"
              strokeWidth={2}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
