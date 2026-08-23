import React from "react";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Database,
  Download,
  FileWarning,
  FileUp,
  Plus,
  RefreshCw,
  ShieldCheck,
  SlidersHorizontal,
  Tags,
  TrendingUp,
  Users
} from "lucide-react";
import type {
  Account,
  Score,
  Alert,
  AccountGroup,
  ImportBatch,
  AlertRule,
  DataSourceVerification,
  ScoreMap,
  AccountStatusFilter,
  OverviewStats
} from "./types";
import { request, requestWithMeta, downloadApiFile } from "./lib/api";
import { scoreTone, formatDate, STATUS_FILTERS } from "./lib/format";
import { KpiCard } from "./components/ui/KpiCard";
import { MetricBar } from "./components/ui/MetricBar";
import { TrendChart } from "./components/ui/TrendChart";
import { ScoreOrb } from "./components/ui/ScoreOrb";
import { StatusPill } from "./components/ui/StatusPill";
import { AlertItem } from "./components/ui/AlertItem";

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
  const [apiToken, setApiToken] = React.useState(() => window.localStorage.getItem("xhs_health_api_token") || "");
  const [showCreate, setShowCreate] = React.useState(false);
  const [statusFilter, setStatusFilter] = React.useState<AccountStatusFilter>("all");
  const [groupFilter, setGroupFilter] = React.useState("all");
  const [page, setPage] = React.useState(1);
  const [pageSize, setPageSize] = React.useState(10);
  const [total, setTotal] = React.useState(0);
  const previousFiltersRef = React.useRef({ status: statusFilter, group: groupFilter });
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

  // Alerts are only ever displayed for the selected account, so fetch them
  // scoped server-side; a global top-N fetch could truncate this account's
  // alerts and wrongly show "no alerts".
  async function refreshAlerts(accountId: number | null) {
    if (accountId == null) {
      setAlerts([]);
      return;
    }
    const nextAlerts = await request<Alert[]>(`/alerts?account_id=${accountId}&limit=100`);
    setAlerts(nextAlerts);
  }

  async function refresh() {
    setLoading(true);
    try {
      const prevFilters = previousFiltersRef.current;
      const filtersChanged = prevFilters.status !== statusFilter || prevFilters.group !== groupFilter;
      if (filtersChanged) {
        previousFiltersRef.current = { status: statusFilter, group: groupFilter };
        setPage(1);
      }
      const params = new URLSearchParams();
      if (statusFilter !== "all") params.set("status", statusFilter);
      if (groupFilter !== "all") params.set("group_id", groupFilter);
      params.set("limit", String(pageSize));
      params.set("offset", String((page - 1) * pageSize));
      const accountPath = `/accounts${params.toString() ? `?${params.toString()}` : ""}`;
      const [accountsResult, nextGroups, nextOverview, nextBatches, nextRules, nextSources] =
        await Promise.all([
          requestWithMeta<Account[]>(accountPath),
          request<AccountGroup[]>("/groups"),
          request<OverviewStats>("/stats/overview"),
          request<ImportBatch[]>("/imports/batches"),
          request<AlertRule[]>("/alerts/rules"),
          request<DataSourceVerification[]>("/data-sources/verifications")
        ]);
      const nextAccounts = accountsResult.data;

      // Build scores map from latest_score returned by /accounts (no N+1).
      const nextScores: ScoreMap = {};
      for (const account of nextAccounts) {
        nextScores[account.id] = account.latest_score ?? null;
      }

      setAccounts(nextAccounts);
      setTotal(accountsResult.total ?? nextAccounts.length);
      setGroups(nextGroups);
      setOverview(nextOverview);
      setImportBatches(nextBatches);
      setAlertRules(nextRules);
      setSources(nextSources);
      setScores(nextScores);
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
  }, [statusFilter, groupFilter, page, pageSize]);

  React.useEffect(() => {
    refreshAlerts(selectedAccount?.id ?? null).catch((error) => setMessage(error.message));
  }, [selectedAccount?.id]);

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
    await Promise.all([
      refreshAlerts(selectedAccount?.id ?? null),
      request<OverviewStats>("/stats/overview").then(setOverview)
    ]);
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
      await Promise.all([
        refreshAlerts(selectedAccount?.id ?? null),
        request<OverviewStats>("/stats/overview").then(setOverview)
      ]);
      setMessage(`已完成 ${batch.length} 个账号评分`);
    } finally {
      setLoading(false);
    }
  }

  async function resolveAlert(alertId: number) {
    await request<Alert>(`/alerts/${alertId}/resolve`, { method: "PUT" });
    await Promise.all([
      refreshAlerts(selectedAccount?.id ?? null),
      request<OverviewStats>("/stats/overview").then(setOverview)
    ]);
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
    if (nextToken.trim()) window.localStorage.setItem("xhs_health_api_token", nextToken.trim());
    else window.localStorage.removeItem("xhs_health_api_token");
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
    const slug = newRule.name.trim()
      .toLowerCase()
      .replace(/[^a-z0-9\u4e00-\u9fa5]+/g, "_")
      .replace(/^_+|_+$/g, "")
      .slice(0, 32) || "custom_rule";
    await request<AlertRule>("/alerts/rules", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: newRule.name.trim(),
        alert_type: `custom_${slug}`,
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
          <span className="brand-logo" aria-hidden="true">
            <Activity size={20} />
          </span>
          <span className="brand-text">
            <span className="brand-name">账号健康监控</span>
            <span className="brand-tag">XHS Health · v0.1</span>
          </span>
        </div>

        <div>
          <div className="sidebar-section-label">工作台</div>
          <nav aria-label="主导航">
            <button className="nav-item active" type="button"><BarChart3 size={17} />总览</button>
            <button className="nav-item" type="button" onClick={() => setShowCreate((value) => !value)}>
              <Plus size={17} />添加账号
            </button>
          </nav>
        </div>

        <div>
          <div className="sidebar-section-label">数据</div>
          <nav aria-label="数据操作">
            <button
              className="nav-item"
              type="button"
              onClick={() => downloadApiFile("/imports/template", "xhs-health-import-template.csv").catch((error) => setMessage(error.message))}
            >
              <Download size={17} />下载模板
            </button>
            <label className="nav-item upload" title="支持 CSV / XLSX">
              <FileUp size={17} />导入数据
              <input
                type="file"
                accept=".csv,.xlsx"
                onChange={(event) => event.target.files?.[0] && uploadFile(event.target.files[0])}
              />
            </label>
            <button
              className="nav-item"
              type="button"
              onClick={() => downloadApiFile("/reports/accounts.csv", "xhs-health-accounts.csv").catch((error) => setMessage(error.message))}
            >
              <Download size={17} />导出报表
            </button>
          </nav>
        </div>

        <div>
          <div className="sidebar-section-label">配置</div>
          <nav aria-label="配置管理">
            <a className="nav-item" href="#panel-groups" title="账号分组管理">
              <Tags size={17} />账号分组
            </a>
            <a className="nav-item" href="#panel-rules" title="告警规则管理">
              <SlidersHorizontal size={17} />告警规则
            </a>
            <a className="nav-item" href="#panel-sources" title="数据源验真管理">
              <Database size={17} />数据源验真
            </a>
          </nav>
        </div>

        <div>
          <div className="sidebar-section-label">日志</div>
          <nav aria-label="日志">
            <a className="nav-item" href="#panel-batches" title="导入批次历史">
              <FileWarning size={17} />导入批次
            </a>
          </nav>
        </div>

        <div className="sidebar-footer">
          <span>{monitoredCount} 个账号在监控</span>
          <span>更新：{new Date().toLocaleDateString("zh-CN")}</span>
        </div>
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
              <input
                value={apiToken}
                onChange={(event) => saveApiToken(event.target.value)}
                placeholder="留空使用默认"
                type="password"
                autoComplete="off"
              />
            </label>
            <button
              className="secondary-action"
              type="button"
              onClick={() => scoreAllAccounts()}
              disabled={loading}
              title="对所有账号重新计算评分"
            >
              <TrendingUp size={16} />
              一键评分
            </button>
            <button
              className="primary-action"
              type="button"
              onClick={() => refresh()}
              disabled={loading}
            >
              {loading ? <span className="spinner" aria-hidden="true" /> : <RefreshCw size={16} />}
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

        <section className="kpis" aria-label="关键指标">
          <KpiCard icon={<Users size={18} />} label="监控账号" value={monitoredCount} hint="总计在库" tone="neutral" />
          <KpiCard icon={<ShieldCheck size={18} />} label="健康账号" value={healthyCount} hint="评分 ≥ 70" tone="good" />
          <KpiCard icon={<AlertTriangle size={18} />} label="预警账号" value={warningCount} hint="评分 55–69" tone="watch" />
          <KpiCard icon={<Activity size={18} />} label="低置信度" value={lowConfidenceCount} hint="需补充数据" tone="muted" />
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
                  <div
                    className={`table-row ${selectedAccount?.id === account.id ? "selected" : ""}`}
                    key={account.id}
                    onClick={() => setSelectedId(account.id)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        setSelectedId(account.id);
                      }
                    }}
                    role="button"
                    tabIndex={0}
                    aria-label={`查看 ${account.nickname} 详情`}
                  >
                    <span>
                      <strong>{account.nickname}</strong>
                      <small className="mono">{account.platform_uid}</small>
                      <StatusPill status={account.status} />
                    </span>
                    <span>
                      <strong className="row-category">{account.category || "未分类"}</strong>
                      <small>{names.join(" / ") || "未分组"}</small>
                    </span>
                    <span className={`score ${scoreTone(score)}`}>{score ? score.total_score.toFixed(1) : "--"}</span>
                    <span className="row-confidence">
                      {score?.confidence_level || "—"}
                    </span>
                    <span className="row-actions">
                      <button
                        type="button"
                        className="link-button"
                        onClick={(event) => { event.stopPropagation(); triggerScore(account.id).catch((error) => setMessage(error.message)); }}
                      >
                        评分
                      </button>
                      {account.status !== "archived" && (
                        <button
                          type="button"
                          className="link-button"
                          onClick={(event) => { event.stopPropagation(); updateAccountStatus(account.id, account.status === "paused" ? "active" : "paused").catch((error) => setMessage(error.message)); }}
                        >
                          {account.status === "paused" ? "恢复" : "暂停"}
                        </button>
                      )}
                      {account.status !== "archived" && (
                        <button
                          type="button"
                          className="link-button danger"
                          onClick={(event) => { event.stopPropagation(); archiveAccount(account.id).catch((error) => setMessage(error.message)); }}
                        >
                          归档
                        </button>
                      )}
                    </span>
                  </div>
                );
              })}
              {total > 0 && (() => {
                const totalPages = Math.max(1, Math.ceil(total / pageSize));
                const gotoPage = (next: number) => setPage(Math.min(totalPages, Math.max(1, next)));
                return (
                  <div className="pager">
                    <button type="button" disabled={page <= 1} onClick={() => gotoPage(1)}>首页</button>
                    <button type="button" disabled={page <= 1} onClick={() => gotoPage(page - 1)}>上一页</button>
                    <span className="pager-info">第 {page} / {totalPages} 页 · 共 {total} 条</span>
                    <button type="button" disabled={page >= totalPages} onClick={() => gotoPage(page + 1)}>下一页</button>
                    <button type="button" disabled={page >= totalPages} onClick={() => gotoPage(totalPages)}>末页</button>
                    <select
                      className="pager-size"
                      value={pageSize}
                      onChange={(event) => { setPage(1); setPageSize(Number(event.target.value)); }}
                    >
                      <option value={10}>10 条/页</option>
                      <option value={20}>20 条/页</option>
                      <option value={50}>50 条/页</option>
                      <option value={100}>100 条/页</option>
                    </select>
                  </div>
                );
              })()}
              {!accounts.length && <div className="empty">暂无账号，上传 CSV/XLSX 或调用导入接口。</div>}
            </div>
          </div>

          <aside className="panel detail-panel" aria-label="账号详情">
            <div className="section-heading">
              <h2>{selectedAccount?.nickname || "账号详情"}</h2>
              <span>{selectedScore ? `${selectedScore.health_level} · ${formatDate(selectedScore.score_date)}` : "—"}</span>
            </div>

            <ScoreOrb score={selectedScore} />

            <TrendChart scores={history} />

            {selectedScore?.data_completeness != null && (
              <div className="subsection" style={{ marginTop: "var(--space-4)" }}>
                <h3>数据完整度</h3>
                <MetricBar label="完整度" value={selectedScore.data_completeness * 100} suffix="%" />
              </div>
            )}

            <div className="subsection">
              <h3>四维评分</h3>
              <div className="breakdown">
                <MetricBar label="数据指标" value={selectedScore?.data_score} />
                <MetricBar label="内容质量" value={selectedScore?.content_score} />
                <MetricBar label="合规风险" value={selectedScore?.compliance_score} />
                <MetricBar label="转化能力" value={selectedScore?.conversion_score} />
              </div>
            </div>

            <div className="subsection">
              <h3>扣分与缺失字段</h3>
              {(selectedScore?.missing_fields || []).slice(0, 5).map((field) => <p className="suggestion" key={field}>{field}</p>)}
              {!selectedScore?.missing_fields.length && (
                <div className="quiet" style={{ display: "flex", alignItems: "center", gap: 8, justifyContent: "center" }}>
                  <CheckCircle2 size={16} style={{ color: "var(--brand-600)" }} />
                  关键字段完整
                </div>
              )}
            </div>

            <div className="subsection">
              <h3>最新告警</h3>
              <div className="alert-list">
                {selectedAlerts.slice(0, 5).map((alert) => (
                  <AlertItem key={alert.id} alert={alert} onResolve={(id) => resolveAlert(id).catch((error) => setMessage(error.message))} />
                ))}
                {!selectedAlerts.length && (
                  <div className="quiet" style={{ display: "flex", alignItems: "center", gap: 8, justifyContent: "center" }}>
                    <CheckCircle2 size={16} style={{ color: "var(--brand-600)" }} />
                    暂无告警
                  </div>
                )}
              </div>
            </div>

            <div className="subsection">
              <h3>优化建议</h3>
              {(selectedScore?.details_json.suggestions || []).slice(0, 3).map((item) => <p className="suggestion" key={item}>{item}</p>)}
              {!selectedScore?.details_json.suggestions?.length && <div className="quiet">暂无建议</div>}
            </div>
          </aside>
        </section>

        <section className="ops-grid">
          <div className="panel" id="panel-groups">
            <div className="section-heading"><h2><Tags size={16} />账号分组</h2></div>
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

          <div className="panel" id="panel-rules">
            <div className="section-heading"><h2><SlidersHorizontal size={16} />告警规则</h2></div>
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

          <div className="panel" id="panel-batches">
            <div className="section-heading"><h2><FileWarning size={16} />导入批次</h2></div>
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

          <div className="panel" id="panel-sources">
            <div className="section-heading"><h2><Database size={16} />数据源验真</h2></div>
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

export default App;
