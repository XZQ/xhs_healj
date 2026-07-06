type Props = {
  label: string;
  value?: number | null;
  suffix?: string;
};

/**
 * MetricBar — 维度评分条。.metric / .bar 样式见 styles.css。
 * 进度条宽度按值 clamp 到 2–100%，与评分球使用同一套 4dp / 色板体系。
 */
export function MetricBar({ label, value, suffix }: Props) {
  const safe = value ?? 0;
  const display = value == null ? "--" : value > 100 ? value.toFixed(0) : value.toFixed(1);
  return (
    <div className="metric">
      <div>
        <span>{label}</span>
        <strong>
          {display}
          {suffix && value != null && (
            <span style={{ fontSize: "11px", fontWeight: 500, color: "var(--text-muted)", marginLeft: 2 }}>
              {suffix}
            </span>
          )}
        </strong>
      </div>
      <div className="bar">
        <i style={{ width: `${Math.max(2, Math.min(100, safe))}%` }} />
      </div>
    </div>
  );
}
