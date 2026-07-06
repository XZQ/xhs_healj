import React from "react";

type KpiTone = "neutral" | "good" | "watch" | "muted";

type Props = {
  icon: React.ReactNode;
  label: string;
  value: number;
  hint?: string;
  tone?: KpiTone;
};

/**
 * KpiCard — 顶部关键指标卡。
 * tone 通过 data-tone 映射到 styles.css 中 .kpi-icon[data-tone] 的语义色。
 */
export function KpiCard({ icon, label, value, hint, tone = "neutral" }: Props) {
  return (
    <div className="kpi">
      <div className="kpi-header">
        <span className="kpi-icon" data-tone={tone}>
          {icon}
        </span>
      </div>
      <span className="kpi-label">{label}</span>
      <strong className="kpi-value">{value}</strong>
      {hint && <span className="kpi-foot">{hint}</span>}
    </div>
  );
}
