import React from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  AlertTriangle,
  Download,
  BarChart3,
  FileUp,
  HeartPulse,
  Plus,
  RefreshCw,
  ShieldCheck,
  Users
} from "lucide-react";
import "./styles.css";

type Account = {
  id: number;
  platform_uid: string;
  nickname: string;
  category?: string | null;
  status: string;
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

type ScoreMap = Record<number, Score | null>;

const API = "/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, init);
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
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
  const [scores, setScores] = React.useState<ScoreMap>({});
  const [alerts, setAlerts] = React.useState<Alert[]>([]);
  const [selectedId, setSelectedId] = React.useState<number | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [uploading, setUploading] = React.useState(false);
  const [message, setMessage] = React.useState("");
  const [showCreate, setShowCreate] = React.useState(false);
  const [newAccount, setNewAccount] = React.useState({
    platform_uid: "",
    nickname: "",
    category: ""
  });

  const selectedAccount = accounts.find((account) => account.id === selectedId) ?? accounts[0];
  const selectedScore = selectedAccount ? scores[selectedAccount.id] : null;

  async function refresh() {
    setLoading(true);
    try {
      const nextAccounts = await request<Account[]>("/accounts");
      setAccounts(nextAccounts);
      if (!selectedId && nextAccounts[0]) setSelectedId(nextAccounts[0].id);
      const entries = await Promise.all(
        nextAccounts.map(async (account) => {
          try {
            const score = await request<Score>(`/scores/${account.id}`);
            return [account.id, score] as const;
          } catch {
            return [account.id, null] as const;
          }
        })
      );
      setScores(Object.fromEntries(entries));
      setAlerts(await request<Alert[]>("/alerts"));
    } finally {
      setLoading(false);
    }
  }

  React.useEffect(() => {
    refresh().catch((error) => setMessage(error.message));
  }, []);

  async function triggerScore(accountId: number) {
    setMessage("");
    const score = await request<Score>("/scores/trigger", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ account_id: accountId })
    });
    setScores((current) => ({ ...current, [accountId]: score }));
    setAlerts(await request<Alert[]>("/alerts"));
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
      setAlerts(await request<Alert[]>("/alerts"));
      setMessage(`已完成 ${batch.length} 个账号评分`);
    } finally {
      setLoading(false);
    }
  }

  async function uploadFile(file: File) {
    setUploading(true);
    setMessage("");
    try {
      const form = new FormData();
      form.append("file", file);
      const result = await request<{ accounts_upserted: number }>("/imports/account-metrics-file", {
        method: "POST",
        body: form
      });
      setMessage(`导入完成：${result.accounts_upserted} 个账号`);
      await refresh();
    } finally {
      setUploading(false);
    }
  }

  function downloadTemplate() {
    window.location.href = `${API}/imports/template`;
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

  const healthyCount = Object.values(scores).filter((score) => score && score.total_score >= 70).length;
  const warningCount = Object.values(scores).filter(
    (score) => score && score.total_score >= 55 && score.total_score < 70
  ).length;
  const lowConfidenceCount = Object.values(scores).filter(
    (score) => score?.confidence_level === "Low"
  ).length;

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
          <button className="nav-item"><Users size={18} />账号</button>
          <button className="nav-item"><AlertTriangle size={18} />告警</button>
          <button className="nav-item" onClick={downloadTemplate}><Download size={18} />模板</button>
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
            <p>按数据完整度、健康评分和告警信号跟踪博主账号。</p>
          </div>
          <div className="top-actions">
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
          <form
            className="create-panel"
            onSubmit={(event) => createAccount(event).catch((error) => setMessage(error.message))}
          >
            <label>
              <span>平台 UID</span>
              <input
                value={newAccount.platform_uid}
                onChange={(event) =>
                  setNewAccount((current) => ({ ...current, platform_uid: event.target.value }))
                }
                required
                placeholder="例如 5a1234567890"
              />
            </label>
            <label>
              <span>昵称</span>
              <input
                value={newAccount.nickname}
                onChange={(event) =>
                  setNewAccount((current) => ({ ...current, nickname: event.target.value }))
                }
                required
                placeholder="博主昵称"
              />
            </label>
            <label>
              <span>赛道</span>
              <input
                value={newAccount.category}
                onChange={(event) =>
                  setNewAccount((current) => ({ ...current, category: event.target.value }))
                }
                placeholder="美妆护肤"
              />
            </label>
            <button type="submit">添加账号</button>
          </form>
        )}

        <section className="kpis">
          <Kpi icon={<Users size={20} />} label="监控账号" value={accounts.length} />
          <Kpi icon={<ShieldCheck size={20} />} label="健康账号" value={healthyCount} />
          <Kpi icon={<AlertTriangle size={20} />} label="预警账号" value={warningCount} />
          <Kpi icon={<Activity size={20} />} label="低置信度" value={lowConfidenceCount} />
        </section>

        <section className="content-grid">
          <div className="panel account-panel">
            <div className="section-heading">
              <h2>账号列表</h2>
              <span>{accounts.length} 条</span>
            </div>
            <div className="table">
              <div className="table-row table-head">
                <span>账号</span>
                <span>赛道</span>
                <span>健康评分</span>
                <span>置信度</span>
                <span>操作</span>
              </div>
              {accounts.map((account) => {
                const score = scores[account.id];
                return (
                  <button
                    className={`table-row ${selectedAccount?.id === account.id ? "selected" : ""}`}
                    key={account.id}
                    onClick={() => setSelectedId(account.id)}
                  >
                    <span>
                      <strong>{account.nickname}</strong>
                      <small>{account.platform_uid}</small>
                    </span>
                    <span>{account.category || "未分类"}</span>
                    <span className={`score ${scoreTone(score)}`}>{score ? score.total_score.toFixed(1) : "待评分"}</span>
                    <span>{score?.confidence_level || "-"}</span>
                    <span>
                      <span
                        className="link-button"
                        onClick={(event) => {
                          event.stopPropagation();
                          triggerScore(account.id).catch((error) => setMessage(error.message));
                        }}
                      >
                        评分
                      </span>
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
            <div className="breakdown">
              <Metric label="数据指标" value={selectedScore?.data_score} />
              <Metric label="内容质量" value={selectedScore?.content_score} />
              <Metric label="合规风险" value={selectedScore?.compliance_score} />
              <Metric label="转化能力" value={selectedScore?.conversion_score} />
            </div>
            <div className="subsection">
              <h3>最新告警</h3>
              <div className="alert-list">
                {alerts.slice(0, 4).map((alert) => (
                  <div className="alert-item" key={alert.id}>
                    <AlertTriangle size={16} />
                    <span>{alert.title}</span>
                  </div>
                ))}
                {!alerts.length && <div className="quiet">暂无告警</div>}
              </div>
            </div>
            <div className="subsection">
              <h3>建议</h3>
              {(selectedScore?.details_json.suggestions || ["暂无建议"]).slice(0, 3).map((item) => (
                <p className="suggestion" key={item}>{item}</p>
              ))}
            </div>
          </aside>
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
      <div className="bar">
        <i style={{ width: `${Math.max(4, Math.min(100, safe))}%` }} />
      </div>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
