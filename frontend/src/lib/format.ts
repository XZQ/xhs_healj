// Pure formatting & scoring helpers (no JSX).
import type { Score } from "../types";

export const STATUS_LABELS: Record<string, string> = {
  active: "监控中",
  paused: "已暂停",
  archived: "已归档"
};

export const STATUS_FILTERS: Array<{ value: "all" | "active" | "paused" | "archived"; label: string }> = [
  { value: "all", label: "全部" },
  { value: "active", label: "监控中" },
  { value: "paused", label: "已暂停" },
  { value: "archived", label: "已归档" }
];

export function scoreTone(score?: Score | null) {
  if (!score) return "muted";
  if (score.total_score >= 85) return "good";
  if (score.total_score >= 70) return "stable";
  if (score.total_score >= 55) return "watch";
  return "risk";
}

export function scoreLabel(score?: Score | null) {
  if (!score) return "待评分";
  if (score.total_score >= 85) return "优秀";
  if (score.total_score >= 70) return "稳健";
  if (score.total_score >= 55) return "关注";
  return "高风险";
}

export function formatDate(iso: string) {
  if (!iso) return "-";
  try {
    return new Date(iso).toLocaleString("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit"
    });
  } catch {
    return iso;
  }
}
