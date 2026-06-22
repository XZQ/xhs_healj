import React from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Database,
  Download,
  FileWarning,
  FileUp,
  HeartPulse,
  Plus,
  RefreshCw,
  ShieldCheck,
  SlidersHorizontal,
  Tags,
  Users
} from "lucide-react";
import "./styles.css";

type Account = {
  id: number;
  platform_uid: string;
  nickname: string;
  category?: string | null;
  status: string;
  group_ids: number[];
};

type Score = {
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

type Alert = {
  id: number;
  account_id: number;
  alert_type: string;
  severity: string;
  title: string;
  message?: string | null;
  is_resolved: boolean;
  created_at: string;
};

type AccountGroup = {
  id: number;
  name: string;
  description?: string | null;
  account_ids: number[];
  created_at: string;
};

type ImportBatch = {
  id: number;
  filename: string;
  total_rows: number;
  valid_rows: number;
  error_rows: number;
  status: string;
  created_at: string;
};

type AlertRule = {
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

type DataSourceVerification = {
  id: number;
  source: string;
  interface_name?: string | null;
  status: string;
  available_fields: string[];
  fallback_strategy?: string | null;
  updated_at: string;
};

type ScoreMap = Record<number, Score | null>;
type AccountStatusFilter = "all" | "active" | "paused" | "archived";

type OverviewStats = {
  monitored_accounts: number;
  healthy_accounts: number;
  warning_accounts: number;
  risky_accounts: number;
  low_confidence_accounts: number;
  unresolved_alerts: number;
};

const API = "/api/v1";
const TOKEN_KEY = "xhs_health_api_token";

const STATUS_LABELS: Record<string, string> = {
  active: "监控中",
  paused: "已暂停",
  archived: "已归档"
};

const STATUS_FILTERS: Array<{ value: AccountStatusFilter; label: string }> = [
  { value: "all", label: "全部" },
  { value: "active", label: "监控中" },
  { value: "paused", label: "已暂停" },
  { value: "archived", label: "已归档" }
];

function getStoredToken() {
  return window.localStorage.getItem(TOKEN_KEY) || "";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  const token = getStoredToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API}${path}`, { ...init, headers });
  if (response.status === 401) throw new Error("AUTH_REQUIRED");
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<T>;
}

async function downloadApiFile(path: string, filename: string) {
  const headers = new Headers();
  const token = getStoredToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API}${path}`, { headers });
  if (response.status === 401) throw new Error("AUTH_REQUIRED");
  if (!response.ok) throw new Error(await response.text());
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

function scoreTone(score?: Score | null) {
  if (!score) return "muted";
  if (score.total_score >= 85) return "good";
  if (score.total_score >= 70) return "stable";
  if (score.total_score >= 55) return "watch";
  return "risk";
}

function App() {
  const [accounts, setAccounts] = React.useState<Account[]>([]);
  const [groups, setGroups] = React.useState<AccountGroup[]>([]);
  const [scores, setScores] = React.useState<ScoreMap>({});
  const [alerts, setAlerts] = React.useState<Alert[]>([]);
  const [overview, setOverview] = React.useState<OverviewStats | null>(null);
  const [history, setHistory] = React.useState<Score[]>([]);
  const [importBatches, setImportBatches] = React.useState<ImportBatch[]>([]);
  const [alertRules, setAlertRules] = React.useState<AlertRule[]>([]);
  const [sources, setSources] = React.useState<DataSourceVerification[]>([]);
  const [selectedId, setSelectedId] = React.useState<number | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [uploading, setUploading] = React.useState(false);
  const [message, setMessage] = React.useState("");
  const [apiToken, setApiToken] = React.useState(() => getStoredToken());
  const [showCreate, setShowCreate] = React.useState(false);
  const [statusFilter, setStatusFilter] = React.useState<AccountStatusFilter>("all");
  const [groupFilter, setGroupFilter] = React.useState("all");
  const [newGroupName, setNewGroupName] = React.useState("");
  const [newAccount, setNewAccount] = React.useState({ platform_uid: "", nickname: "", category: "" });
  const [newRule, setNewRule] = React.useState({
    name: "",
    metric_name: "total_score",
    operator: "lt" as AlertRule["operator"],
    threshold_value: 55
  });
  const [newSource, setNewSource] = React.useState({ source: "", interface_name: "" });

  const selectedAccount = accounts.find((account) => account.id === selectedId) ?? accounts[0];
  const selectedScore = selectedAccount ? scores[selectedAccount.id] : null;
  const selectedAlerts = selectedAccount
    ? alerts.filter((alert) => alert.account_id === selectedAccount.id)
    : alerts;

  async function refresh() {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (statusFilter !== "all") params.set("status", statusFilter);
      if (groupFilter !== "all") params.set("group_id", groupFilter);
      const accountPath = `/accounts${params.toString() ? `?${params.toString()}` : ""}`;
      const [nextAccounts, nextGroups, nextAlerts, nextOverview, nextBatches, nextRules, nextSources] =
        await Promise.all([
          request<Account[]>(accountPath),
          request<AccountGroup[]>("/groups"),
          request<Alert[]>("/alerts"),
          request<OverviewStats>("/stats/overview"),
          request<ImportBatch[]>("/imports/batches"),
          request<AlertRule[]>("/alerts/rules"),
          request<DataSourceVerification[]>("/data-sources/verifications")
        ]);

      const scoreEntries = await Promise.all(
        nextAccounts.map(async (account) => {
          try {
            return [account.id, await request<Score>(`/scores/${account.id}`)] as const;
          } catch {
            return [account.id, null] as const;
          }
        })
      );

      setAccounts(nextAccounts);
      setGroups(nextGroups);
      setAlerts(nextAlerts);
      setOverview(nextOverview);
      setImportBatches(nextBatches);
      setAlertRules(nextRules);
      setSources(nextSources);
      setScores(Object.fromEntries(scoreEntries));
      if (nextAccounts.length && !nextAccounts.some((account) => account.id === selectedId)) {
        setSelectedId(nextAccounts[0].id);
      }
      if (!nextAccounts.length) setSelectedId(null);
    } finally {
      setLoading(false);
    }
  }

  React.useEffect(() => {
    refresh().catch((error) => setMessage(error.message));
  }, [statusFilter, groupFilter]);

  React.useEffect(() => {
    if (!selectedAccount) {
      setHistory([]);
      return;
    }
    request<Score[]>(`/scores/${selectedAccount.id}/history`)
      .then((items) => setHistory([...items].reverse().slice(-30)))
      .catch(() => setHistory([]));
  }, [selectedAccount?.id]);

  async function triggerScore(accountId: number) {
    setMessage("");
    const score = await request<Score>("/scores/trigger", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ account_id: accountId })
    });
    setScores((current) => ({ ...current, [accountId]: score }));
    const [nextAlerts, nextOverview] = await Promise.all([
      request<Alert[]>("/alerts"),
      request<OverviewStats>("/stats/overview")
    ]);
    setAlerts(nextAlerts);
    setOverview(nextOverview);
  }

  async function scoreAllAccounts() {
    setLoading(true);
    setMessage("");
    try {
      const batch = await request<Score[]>("/scores/batch-trigger", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({})
      });
      setScores((current) => ({
        ...current,
        ...Object.fromEntries(batch.map((score) => [score.account_id, score]))
      }));
      const [nextAlerts, nextOverview] = await Promise.all([
        request<Alert[]>("/alerts"),
        request<OverviewStats>("/stats/overview")
      ]);
      setAlerts(nextAlerts);
      setOverview(nextOverview);
      setMessage(`已完成 ${batch.length} 个账号评分`);
    } finally {
      setLoading(false);
    }
  }

  async function resolveAlert(alertId: number) {
    await request<Alert>(`/alerts/${alertId}/resolve`, { method: "PUT" });
    const [nextAlerts, nextOverview] = await Promise.all([
      request<Alert[]>("/alerts"),
      request<OverviewStats>("/stats/overview")
    ]);
    setAlerts(nextAlerts);
    setOverview(nextOverview);
  }

  async function updateAccountStatus(accountId: number, status: "active" | "paused") {
    await request<Account>(`/accounts/${accountId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status })
    });
    await refresh();
  }

  async function archiveAccount(accountId: number) {
    await request<Account>(`/accounts/${accountId}`, { method: "DELETE" });
    await refresh();
  }

  async function uploadFile(file: File) {
    setUploading(true);
    setMessage("");
    try {
      const form = new FormData();
      form.append("file", file);
      const result = await request<{ accounts_upserted: number; import_batch_id?: number; error_rows: number }>(
        "/imports/account-metrics-file",
        { method: "POST", body: form }
      );
      const errorText = result.error_rows ? `，${result.error_rows} 行有错误，可下载错误报告` : "";
      setMessage(`导入完成：${result.accounts_upserted} 个账号${errorText}`);
      await refresh();
    } finally {
      setUploading(false);
    }
  }

  function saveApiToken(nextToken: string) {
    setApiToken(nextToken);
    if (nextToken.trim()) window.localStorage.setItem(TOKEN_KEY, nextToken.trim());
    else window.localStorage.removeItem(TOKEN_KEY);
  }

  async function createAccount(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage("");
    const account = await request<Account>("/accounts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        platform_uid: newAccount.platform_uid.trim(),
        nickname: newAccount.nickname.trim(),
        category: newAccount.category.trim() || null
      })
    });
    setNewAccount({ platform_uid: "", nickname: "", category: "" });
    setShowCreate(false);
    setSelectedId(account.id);
    await refresh();
  }

  async function createGroup() {
    if (!newGroupName.trim()) return;
    await request<AccountGroup>("/groups", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: newGroupName.trim() })
    });
    setNewGroupName("");
    await refresh();
  }

  async function addSelectedToGroup(group: AccountGroup) {
    if (!selectedAccount) return;
    const accountIds = Array.from(new Set([...group.account_ids, selectedAccount.id]));
    await request<AccountGroup>(`/groups/${group.id}/members`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ account_ids: accountIds })
    });
    await refresh();
  }

  async function createAlertRule() {
    if (!newRule.name.trim()) return;
    await request<AlertRule>("/alerts/rules", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: newRule.name.trim(),
        alert_type: `custom_${Date.now()}`,
        metric_name: newRule.metric_name,
        operator: newRule.operator,
        threshold_value: newRule.threshold_value,
        severity: "warning",
        enabled: true,
        cooldown_minutes: 1440
      })
    });
    setNewRule({ name: "", metric_name: "total_score", operator: "lt", threshold_value: 55 });
    await refresh();
  }

  async function createDataSource() {
    if (!newSource.source.trim()) return;
    await request<DataSourceVerification>("/data-sources/verifications", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source: newSource.source.trim(),
        interface_name: newSource.interface_name.trim() || null,
        status: "pending",
        fallback_strategy: "手动导入 / 缓存 / 跳过评分",
        available_fields: []
      })
    });
    setNewSource({ source: "", interface_name: "" });
    await refresh();
  }

  const monitoredCount = overview?.monitored_accounts ?? accounts.length;
  const healthyCount =
    overview?.healthy_accounts ?? Object.values(scores).filter((score) => score && score.total_score >= 70).length;
  const warningCount =
    overview?.warning_accounts ??
    Object.values(scores).filter((score) => score && score.total_score >= 55 && score.total_score < 70).length;
  const lowConfidenceCount =
    overview?.low_confidence_accounts ??
    Object.values(scores).filter((score) => score?.confidence_level === "Low").length;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <HeartPulse size={23} />
          <span>账号健康监控</span>
        </div>
        <nav>
          <button className="nav-item active"><BarChart3 size={18} />总览</button>
          <button className="nav-item" onClick={() => setShowCreate((value) => !value)}>
            <Plus size={18} />添加
          </button>
          <button
            className="nav-item"
            onClick={() => downloadApiFile("/imports/template", "xhs-health-import-template.csv").catch((error) => setMessage(error.message))}
          >
            <Download size={18} />模板
          </button>
          <button
            className="nav-item"
            onClick={() => downloadApiFile("/reports/accounts.csv", "xhs-health-accounts.csv").catch((error) => setMessage(error.message))}
          >
            <Download size={18} />报表
          </button>
          <label className="nav-item upload">
            <FileUp size={18} />导入
            <input
              type="file"
              accept=".csv,.xlsx"
              onChange={(event) => event.target.files?.[0] && uploadFile(event.target.files[0])}
            />
          </label>
        </nav>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div>
            <h1>账号健康监控</h1>
            <p>按评分、置信度、告警和数据源验真状态管理博主账号。</p>
          </div>
          <div className="top-actions">
            <label className="token-control">
              <span>API Token</span>
              <input value={apiToken} onChange={(event) => saveApiToken(event.target.value)} placeholder="可选" type="password" />
            </label>
            <button className="secondary-action" onClick={() => scoreAllAccounts()} disabled={loading}>
              <Activity size={17} />
              一键评分
            </button>
            <button className="primary-action" onClick={() => refresh()} disabled={loading}>
              <RefreshCw size={17} />
              {loading ? "刷新中" : "刷新"}
            </button>
          </div>
        </header>

        {message && <div className="notice">{message}</div>}
        {uploading && <div className="notice muted">正在导入文件...</div>}

        {showCreate && (
          <form className="create-panel" onSubmit={(event) => createAccount(event).catch((error) => setMessage(error.message))}>
            <label>
              <span>平台 UID</span>
              <input value={newAccount.platform_uid} onChange={(event) => setNewAccount((current) => ({ ...current, platform_uid: event.target.value }))} required placeholder="例如 5a1234567890" />
            </label>
            <label>
              <span>昵称</span>
              <input value={newAccount.nickname} onChange={(event) => setNewAccount((current) => ({ ...current, nickname: event.target.value }))} required placeholder="博主昵称" />
            </label>
            <label>
              <span>赛道</span>
              <input value={newAccount.category} onChange={(event) => setNewAccount((current) => ({ ...current, category: event.target.value }))} placeholder="美妆护肤" />
            </label>
            <button type="submit">添加账号</button>
          </form>
        )}

        <section className="kpis">
          <Kpi icon={<Users size={20} />} label="监控账号" value={monitoredCount} />
          <Kpi icon={<ShieldCheck size={20} />} label="健康账号" value={healthyCount} />
          <Kpi icon={<AlertTriangle size={20} />} label="预警账号" value={warningCount} />
          <Kpi icon={<Activity size={20} />} label="低置信度" value={lowConfidenceCount} />
        </section>

        <section className="content-grid">
          <div className="panel account-panel">
            <div className="section-heading">
              <h2>账号列表</h2>
              <div className="status-filters">
                {STATUS_FILTERS.map((item) => (
                  <button className={statusFilter === item.value ? "active" : ""} key={item.value} onClick={() => setStatusFilter(item.value)} type="button">
                    {item.label}
                  </button>
                ))}
                <select value={groupFilter} onChange={(event) => setGroupFilter(event.target.value)}>
                  <option value="all">全部分组</option>
                  {groups.map((group) => <option key={group.id} value={group.id}>{group.name}</option>)}
                </select>
              </div>
            </div>
            <div className="table">
              <div className="table-row table-head">
                <span>账号</span>
                <span>赛道/分组</span>
                <span>健康评分</span>
                <span>置信度</span>
                <span>操作</span>
              </div>
              {accounts.map((account) => {
                const score = scores[account.id];
                const names = groups.filter((group) => account.group_ids.includes(group.id)).map((group) => group.name);
                return (
                  <button className={`table-row ${selectedAccount?.id === account.id ? "selected" : ""}`} key={account.id} onClick={() => setSelectedId(account.id)}>
                    <span>
                      <strong>{account.nickname}</strong>
                      <small>{account.platform_uid}</small>
                      <small className={`status-pill ${account.status}`}>{STATUS_LABELS[account.status] ?? account.status}</small>
                    </span>
                    <span>{account.category || "未分类"}<small>{names.join(" / ") || "未分组"}</small></span>
                    <span className={`score ${scoreTone(score)}`}>{score ? score.total_score.toFixed(1) : "待评分"}</span>
                    <span>{score?.confidence_level || "-"}</span>
                    <span className="row-actions">
                      <span className="link-button" onClick={(event) => { event.stopPropagation(); triggerScore(account.id).catch((error) => setMessage(error.message)); }}>评分</span>
                      {account.status !== "archived" && (
                        <span className="link-button" onClick={(event) => { event.stopPropagation(); updateAccountStatus(account.id, account.status === "paused" ? "active" : "paused").catch((error) => setMessage(error.message)); }}>
                          {account.status === "paused" ? "恢复" : "暂停"}
                        </span>
                      )}
                      {account.status !== "archived" && (
                        <span className="link-button danger" onClick={(event) => { event.stopPropagation(); archiveAccount(account.id).catch((error) => setMessage(error.message)); }}>归档</span>
                      )}
                    </span>
                  </button>
                );
              })}
              {!accounts.length && <div className="empty">暂无账号，上传 CSV/XLSX 或调用导入接口。</div>}
            </div>
          </div>

          <aside className="panel detail-panel">
            <div className="section-heading">
              <h2>{selectedAccount?.nickname || "账号详情"}</h2>
              <span>{selectedScore?.health_level || "-"}</span>
            </div>
            <div className={`score-orb ${scoreTone(selectedScore)}`}>
              <strong>{selectedScore ? selectedScore.total_score.toFixed(1) : "--"}</strong>
              <span>健康评分</span>
            </div>
            <Trend scores={history} />
            <div className="breakdown">
              <Metric label="数据指标" value={selectedScore?.data_score} />
              <Metric label="内容质量" value={selectedScore?.content_score} />
              <Metric label="合规风险" value={selectedScore?.compliance_score} />
              <Metric label="转化能力" value={selectedScore?.conversion_score} />
            </div>
            <div className="subsection">
              <h3>扣分与缺失</h3>
              {(selectedScore?.missing_fields || []).slice(0, 5).map((field) => <p className="suggestion" key={field}>{field}</p>)}
              {!selectedScore?.missing_fields.length && <div className="quiet">关键字段完整</div>}
            </div>
            <div className="subsection">
              <h3>最新告警</h3>
              <div className="alert-list">
                {selectedAlerts.slice(0, 5).map((alert) => (
                  <div className={`alert-item ${alert.severity}`} key={alert.id}>
                    <AlertTriangle size={16} />
                    <span>{alert.title}</span>
                    {!alert.is_resolved && <button onClick={() => resolveAlert(alert.id).catch((error) => setMessage(error.message))}>处理</button>}
                  </div>
                ))}
                {!selectedAlerts.length && <div className="quiet">暂无告警</div>}
              </div>
            </div>
            <div className="subsection">
              <h3>建议</h3>
              {(selectedScore?.details_json.suggestions || ["暂无建议"]).slice(0, 3).map((item) => <p className="suggestion" key={item}>{item}</p>)}
            </div>
          </aside>
        </section>

        <section className="ops-grid">
          <div className="panel">
            <div className="section-heading"><h2><Tags size={17} />账号分组</h2></div>
            <div className="inline-form">
              <input value={newGroupName} onChange={(event) => setNewGroupName(event.target.value)} placeholder="新分组名称" />
              <button onClick={() => createGroup().catch((error) => setMessage(error.message))}>创建</button>
            </div>
            <div className="compact-list">
              {groups.map((group) => (
                <div className="compact-row" key={group.id}>
                  <span>{group.name}<small>{group.account_ids.length} 个账号</small></span>
                  <button onClick={() => addSelectedToGroup(group).catch((error) => setMessage(error.message))}>加入当前账号</button>
                </div>
              ))}
              {!groups.length && <div className="quiet">暂无分组</div>}
            </div>
          </div>

          <div className="panel">
            <div className="section-heading"><h2><SlidersHorizontal size={17} />告警规则</h2></div>
            <div className="rule-form">
              <input value={newRule.name} onChange={(event) => setNewRule((current) => ({ ...current, name: event.target.value }))} placeholder="规则名称" />
              <select value={newRule.metric_name} onChange={(event) => setNewRule((current) => ({ ...current, metric_name: event.target.value }))}>
                <option value="total_score">健康分</option>
                <option value="interaction_rate">互动率</option>
                <option value="fans_delta">粉丝增量</option>
                <option value="data_completeness">数据完整度</option>
                <option value="shadowban_risk">限流风险</option>
              </select>
              <select value={newRule.operator} onChange={(event) => setNewRule((current) => ({ ...current, operator: event.target.value as AlertRule["operator"] }))}>
                <option value="lt">&lt;</option>
                <option value="lte">&lt;=</option>
                <option value="gt">&gt;</option>
                <option value="gte">&gt;=</option>
              </select>
              <input type="number" step="0.01" value={newRule.threshold_value} onChange={(event) => setNewRule((current) => ({ ...current, threshold_value: Number(event.target.value) }))} />
              <button onClick={() => createAlertRule().catch((error) => setMessage(error.message))}>添加</button>
            </div>
            <div className="compact-list">
              {alertRules.map((rule) => <div className="compact-row" key={rule.id}><span>{rule.name}<small>{rule.metric_name} {rule.operator} {rule.threshold_value}</small></span><b>{rule.enabled ? "启用" : "停用"}</b></div>)}
              {!alertRules.length && <div className="quiet">暂无自定义规则，内置规则仍会生效</div>}
            </div>
          </div>

          <div className="panel">
            <div className="section-heading"><h2><FileWarning size={17} />导入批次</h2></div>
            <div className="compact-list">
              {importBatches.slice(0, 6).map((batch) => (
                <div className="compact-row" key={batch.id}>
                  <span>{batch.filename}<small>{batch.valid_rows}/{batch.total_rows} 行有效，{batch.error_rows} 行错误</small></span>
                  {batch.error_rows > 0 && <button onClick={() => downloadApiFile(`/imports/batches/${batch.id}/errors.csv`, `import-errors-${batch.id}.csv`).catch((error) => setMessage(error.message))}>错误报告</button>}
                </div>
              ))}
              {!importBatches.length && <div className="quiet">暂无导入批次</div>}
            </div>
          </div>

          <div className="panel">
            <div className="section-heading"><h2><Database size={17} />数据源验真</h2></div>
            <div className="inline-form">
              <input value={newSource.source} onChange={(event) => setNewSource((current) => ({ ...current, source: event.target.value }))} placeholder="数据平台" />
              <input value={newSource.interface_name} onChange={(event) => setNewSource((current) => ({ ...current, interface_name: event.target.value }))} placeholder="接口名称" />
              <button onClick={() => createDataSource().catch((error) => setMessage(error.message))}>登记</button>
            </div>
            <div className="compact-list">
              {sources.map((source) => <div className="compact-row" key={source.id}><span>{source.source}<small>{source.interface_name || "未填接口"} · {source.fallback_strategy || "未填降级策略"}</small></span><b>{source.status}</b></div>)}
              {!sources.length && <div className="quiet">蒲公英/第三方平台接入前需先登记验真</div>}
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}

function Kpi({ icon, label, value }: { icon: React.ReactNode; label: string; value: number }) {
  return (
    <div className="kpi">
      <span className="kpi-icon">{icon}</span>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function Metric({ label, value }: { label: string; value?: number | null }) {
  const safe = value ?? 0;
  return (
    <div className="metric">
      <div>
        <span>{label}</span>
        <strong>{value == null ? "--" : value.toFixed(1)}</strong>
      </div>
      <div className="bar"><i style={{ width: `${Math.max(4, Math.min(100, safe))}%` }} /></div>
    </div>
  );
}

function Trend({ scores }: { scores: Score[] }) {
  if (!scores.length) return <div className="trend empty-trend">暂无历史趋势</div>;
  const width = 300;
  const height = 88;
  const points = scores.map((score, index) => {
    const x = scores.length === 1 ? width / 2 : (index / (scores.length - 1)) * width;
    const y = height - (Math.max(0, Math.min(100, score.total_score)) / 100) * height;
    return `${x},${y}`;
  }).join(" ");
  return (
    <div className="trend">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="近 30 天评分趋势">
        <polyline points={points} fill="none" stroke="#0f8f83" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <div className="trend-caption">
        <span>近 30 天趋势</span>
        <strong>{scores[scores.length - 1]?.total_score.toFixed(1)}</strong>
      </div>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
