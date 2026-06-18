# xhs_healj

小红书博主账号健康度评估系统 MVP。

当前版本先实现后端闭环：

- 账号管理
- JSON 数据导入
- 账号每日快照与笔记每日指标入库
- 四维度健康评分
- 数据完整度与置信度
- 评分历史查询
- 基础告警记录

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[dev]"
uvicorn xhs_health.main:app --reload
```

默认使用本地 SQLite 数据库 `./xhs_health.sqlite3`。生产环境可通过环境变量切换 PostgreSQL：

```powershell
$env:DATABASE_URL = "postgresql+psycopg://user:password@localhost:5432/xhs_health"
```

## Frontend

```powershell
cd frontend
npm install
npm run dev
```

打开：

- API: http://127.0.0.1:8000/api/v1/health
- Dashboard: http://127.0.0.1:5173

前端开发服务器会把 `/api` 代理到 `http://127.0.0.1:8000`。

## Database Migrations

MVP 仍会在应用启动时自动创建 SQLite 表，方便开发快速运行。正式环境建议使用 Alembic：

```powershell
alembic upgrade head
```

## Core APIs

| Method | Path | Description |
|------|------|------|
| `GET` | `/api/v1/health` | health check |
| `POST` | `/api/v1/accounts` | create an account |
| `GET` | `/api/v1/accounts` | list accounts |
| `POST` | `/api/v1/imports/accounts` | import account snapshots and note metrics |
| `POST` | `/api/v1/imports/account-metrics-file` | import CSV/XLSX account metrics |
| `POST` | `/api/v1/scores/trigger` | calculate score |
| `GET` | `/api/v1/scores/{account_id}` | latest score |
| `GET` | `/api/v1/scores/{account_id}/history` | score history |
| `GET` | `/api/v1/alerts` | list alerts |

## CSV/XLSX Import

可以直接在前端上传 `examples/sample_import.csv`，或用 API 上传 CSV/XLSX。核心列：

```text
platform_uid,nickname,category,data_date,fans_count,fans_delta,total_reads,total_likes,total_collects,total_comments,total_shares,publish_count,violation_count_180d,ad_compliance_rate,audit_pass_rate,shadowban_risk,fan_quality_score,cpe,avg_cpe_benchmark,business_stability
```

可选笔记列：

```text
note_id,note_title,content_type,is_ad,is_repost,tags,read_count,like_count,collect_count,comment_count,share_count
```

## Example Import

```json
{
  "accounts": [
    {
      "platform_uid": "5a1234567890",
      "nickname": "示例博主",
      "category": "美妆护肤",
      "fan_quality_score": 0.72,
      "cpe": 2.1,
      "avg_cpe_benchmark": 3.0,
      "business_stability": 0.86,
      "violation_count_180d": 0,
      "ad_compliance_rate": 1.0,
      "audit_pass_rate": 0.98,
      "shadowban_risk": 0.04,
      "snapshots": [
        {
          "data_date": "2026-06-19",
          "fans_count": 52000,
          "fans_delta": 320,
          "notes_count": 120,
          "total_reads": 180000,
          "total_likes": 8200,
          "total_collects": 5100,
          "total_comments": 920,
          "total_shares": 310,
          "publish_count": 1,
          "data_source": "manual"
        }
      ],
      "notes": [
        {
          "note_id": "note_001",
          "title": "夏季护肤清单",
          "content_type": "image",
          "publish_time": "2026-06-19T10:00:00+08:00",
          "is_ad": false,
          "is_original": true,
          "tags": ["护肤", "夏季"],
          "metrics": [
            {
              "data_date": "2026-06-19",
              "read_count": 30000,
              "like_count": 1800,
              "collect_count": 1200,
              "comment_count": 180,
              "share_count": 70,
              "data_source": "manual"
            }
          ]
        }
      ]
    }
  ]
}
```

## Tests

```powershell
pytest
```

## Feishu Document Upload

This project includes a CLI helper for importing local documents into Feishu/Lark Docs.
It uses the official OpenAPI flow: get `tenant_access_token`, upload the source file,
create an import task, then poll for the final document URL.

One-time local setup:

```powershell
$env:FEISHU_APP_ID = "cli_aabe8c4f83b8dce7"
$env:FEISHU_APP_SECRET = "your_app_secret"
$env:FEISHU_FOLDER_TOKEN = "fldxxxx"  # optional; empty imports to the root mount
```

Or create a local `.env` file from `.env.example`; the upload command loads `.env` automatically.

Upload a Markdown file as a Feishu `docx` cloud document:

```powershell
python -m xhs_health.tools.feishu_upload ".\小红书博主账号健康度评估系统-MVP落地方案.md" --title "小红书博主账号健康度评估系统 MVP落地方案"
```

After editable install, the console script is also available:

```powershell
python -m pip install -e .
feishu-upload-doc ".\小红书博主账号健康度评估系统-技术设计方案.md" --title "小红书博主账号健康度评估系统 技术设计方案"
```

If the default source upload API is rejected by your app permissions, retry with:

```powershell
feishu-upload-doc ".\report.md" --source-upload file
```
