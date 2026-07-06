import { STATUS_LABELS } from "../../lib/format";

/**
 * StatusPill — 账号状态标签（监控中 / 已暂停 / 已归档）。
 * 颜色由 .status-pill.{status} 在 styles.css 中映射。
 */
export function StatusPill({ status }: { status: string }) {
  return (
    <small className={`status-pill ${status}`} aria-label={`状态：${STATUS_LABELS[status] ?? status}`}>
      {STATUS_LABELS[status] ?? status}
    </small>
  );
}
