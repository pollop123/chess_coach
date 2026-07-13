import {
  Area,
  ComposedChart,
  Line,
  ReferenceArea,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

function getMoveDotColor(classification) {
  if (classification === "blunder") return "#ef4444";
  if (classification === "mistake") return "#ff7f50";
  if (classification === "inaccuracy") return "#f4a259";
  return null;
}

function EvalDot({ cx, cy, payload }) {
  const color = getMoveDotColor(payload?.classification);
  if (!payload?.move || !color) return null;
  return (
    <circle
      cx={cx}
      cy={cy}
      r={payload.classification === "blunder" ? 7 : 6}
      fill={color}
      stroke="#ffffff"
      strokeWidth={payload.classification === "blunder" ? 2 : 1}
    />
  );
}

function EvalTooltip({ active, payload, label }) {
  if (!active || !payload || payload.length === 0) return null;
  const point = payload[0].payload;
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip__label">第 {label} 步</div>
      <div className="chart-tooltip__value">{point.evalLabel}</div>
    </div>
  );
}

export default function EvaluationChart({ analysisData, currentMoveIndex, onMoveSelect }) {
  return (
    <div className="analysis-card">
      <div className="chart-header">
        <span>局勢走勢（白方視角）</span>
        <span>0 線</span>
      </div>
      <ResponsiveContainer width="100%" height={142}>
        <ComposedChart
          data={analysisData}
          margin={{ top: 8, right: 10, bottom: 8, left: 10 }}
          onClick={(event) => {
            if (event?.activePayload) onMoveSelect(event.activePayload[0].payload.move_number);
          }}
        >
          <defs>
            <linearGradient id="blackAdvantageArea" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#33312d" stopOpacity={1}/>
              <stop offset="100%" stopColor="#4a4741" stopOpacity={0.96}/>
            </linearGradient>
          </defs>
          <XAxis dataKey="move_number" hide />
          <YAxis hide domain={[-1000, 1000]} />
          <Tooltip
            cursor={{ stroke: "#8f8a83", strokeWidth: 1 }}
            content={EvalTooltip}
          />
          <ReferenceArea y1={-1000} y2={1000} fill="#3a3833" fillOpacity={1} />
          <ReferenceLine y={0} stroke="#beb9b1" strokeWidth={3} />
          <Area
            type="monotone"
            dataKey="displayScore"
            baseValue={-1000}
            stroke="#f7f6f3"
            strokeWidth={5}
            fill="#f7f6f3"
            fillOpacity={1}
            isAnimationActive={false}
          />
          <Line
            type="monotone"
            dataKey="displayScore"
            stroke="#f7f6f3"
            dot={false}
            strokeWidth={5}
            isAnimationActive={false}
            activeDot={{ r: 7, fill: "#ffffff", stroke: "#4a4741", strokeWidth: 2 }}
          />
          <Scatter
            data={analysisData.filter((item) => item.move && item.classification !== "good")}
            dataKey="displayScore"
            shape={EvalDot}
            isAnimationActive={false}
          />
          {currentMoveIndex !== -1 && analysisData[currentMoveIndex] && (
            <ReferenceDot
              x={analysisData[currentMoveIndex].move_number}
              y={analysisData[currentMoveIndex].displayScore}
              r={8}
              fill="transparent"
              stroke="#ffffff"
              strokeWidth={3}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
