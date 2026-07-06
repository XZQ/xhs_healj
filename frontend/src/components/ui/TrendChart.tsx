import type { Score } from "../../types";

/**
 * TrendChart — 近 30 天评分趋势（SVG 面积图）。
 * 渐变与描边复用 styles.css 中的 brand token。
 */
export function TrendChart({ scores }: { scores: Score[] }) {
  if (!scores.length) return <div className="trend empty-trend">暂无历史趋势</div>;

  const width = 320;
  const height = 80;
  const padY = 6;
  const points = scores.map((score, index) => {
    const x = scores.length === 1 ? width / 2 : (index / (scores.length - 1)) * width;
    const y = height - padY - (Math.max(0, Math.min(100, score.total_score)) / 100) * (height - padY * 2);
    return [x, y] as const;
  });
  const linePoints = points.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const last = points[points.length - 1];
  const first = points[0];
  const areaPath = `M ${first[0].toFixed(1)},${height} L ${points
    .map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`)
    .join(" L ")} L ${last[0].toFixed(1)},${height} Z`;
  const latest = scores[scores.length - 1];
  const delta = scores.length > 1 ? latest.total_score - scores[scores.length - 2].total_score : 0;

  return (
    <div className="trend">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="近 30 天评分趋势" preserveAspectRatio="none">
        <defs>
          <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--brand-500)" stopOpacity="0.22" />
            <stop offset="100%" stopColor="var(--brand-500)" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="trendLine" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="var(--brand-600)" />
            <stop offset="100%" stopColor="var(--brand-700)" />
          </linearGradient>
        </defs>
        <path d={areaPath} fill="url(#trendFill)" />
        <polyline
          points={linePoints}
          fill="none"
          stroke="url(#trendLine)"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
        />
        <circle cx={last[0]} cy={last[1]} r="3.5" fill="var(--brand-700)" stroke="#fff" strokeWidth="1.5" />
      </svg>
      <div className="trend-caption">
        <span>近 {scores.length} 次评分</span>
        <strong>
          {latest.total_score.toFixed(1)}
          {scores.length > 1 && (
            <span
              style={{
                marginLeft: 6,
                fontSize: 11,
                fontWeight: 600,
                color: delta >= 0 ? "var(--success-fg)" : "var(--danger-fg)"
              }}
            >
              {delta >= 0 ? "▲" : "▼"} {Math.abs(delta).toFixed(1)}
            </span>
          )}
        </strong>
      </div>
    </div>
  );
}
