import React from "react";
import { AlertTriangle, Info, AlertOctagon } from "lucide-react";
import type { Alert } from "../../types";

const ALERT_ICONS: Record<string, React.ReactNode> = {
  info: <Info size={15} />,
  warning: <AlertTriangle size={15} />,
  critical: <AlertOctagon size={15} />
};

/**
 * AlertItem — 告警行。severity 决定配色（.alert-item.info/.warning/.critical）
 * 与图标，是告警正确性的关键组件。
 */
export function AlertItem({ alert, onResolve }: { alert: Alert; onResolve?: (id: number) => void }) {
  return (
    <div className={`alert-item ${alert.severity}`}>
      {ALERT_ICONS[alert.severity] ?? <AlertTriangle size={15} />}
      <span>{alert.title}</span>
      {!alert.is_resolved && onResolve && (
        <button type="button" onClick={() => onResolve(alert.id)}>
          标记处理
        </button>
      )}
    </div>
  );
}
