export type Account = {
  id: number;
  platform_uid: string;
  nickname: string;
  category?: string | null;
  status: string;
  group_ids: number[];
  latest_score?: Score | null;
};

export type Score = {
  id: number;
  account_id: number;
  score_date: string;
  total_score: number;
  health_level: string;
  confidence_level?: string | null;
  data_completeness?: number | null;
  data_score?: number | null;
  content_score?: number | null;
  compliance_score?: number | null;
  conversion_score?: number | null;
  details_json: {
    suggestions?: string[];
    dimensions?: Record<string, { name: string; final_score: number | null; penalty_reasons: string[] }>;
  };
  missing_fields: string[];
  warning_flags: string[];
};

export type Alert = {
  id: number;
  account_id: number;
  alert_type: string;
  severity: string;
  title: string;
  message?: string | null;
  is_resolved: boolean;
  created_at: string;
};

export type AccountGroup = {
  id: number;
  name: string;
  description?: string | null;
  account_ids: number[];
  created_at: string;
};

export type ImportBatch = {
  id: number;
  filename: string;
  total_rows: number;
  valid_rows: number;
  error_rows: number;
  status: string;
  created_at: string;
};

export type AlertRule = {
  id: number;
  name: string;
  alert_type: string;
  metric_name: string;
  operator: "lt" | "lte" | "gt" | "gte" | "eq";
  threshold_value: number;
  severity: "info" | "warning" | "critical";
  enabled: boolean;
  cooldown_minutes: number;
  created_at: string;
};

export type DataSourceVerification = {
  id: number;
  source: string;
  interface_name?: string | null;
  status: string;
  available_fields: string[];
  fallback_strategy?: string | null;
  updated_at: string;
};

export type ScoreMap = Record<number, Score | null>;
export type AccountStatusFilter = "all" | "active" | "paused" | "archived";

export type OverviewStats = {
  monitored_accounts: number;
  healthy_accounts: number;
  warning_accounts: number;
  risky_accounts: number;
  low_confidence_accounts: number;
  unresolved_alerts: number;
};
