# 小红书博主账号健康度评估系统 — MVP 落地方案

| 属性 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 编写日期 | 2026-06-19 |
| 适用阶段 | MVP / 内测验证 |
| 目标周期 | 4-6 周 |
| 设计目标 | 先跑通评分闭环，再逐步生产化 |

---

## 1. MVP 目标

MVP 阶段不追求一次性完成完整生产平台，而是验证三件事：

1. 数据是否能稳定进入系统。
2. 健康评分是否可解释、可复核。
3. 看板/API 是否能支撑真实业务判断。

MVP 的交付标准是：用户可以录入或导入博主账号数据，系统可以计算健康分、展示评分明细、输出扣分原因，并保留历史评分趋势。

---

## 2. 范围边界

### 2.1 MVP 必做

| 模块 | 功能 | 说明 |
|------|------|------|
| 账号管理 | 添加、编辑、停用、分组 | 支持平台 UID、昵称、赛道、标签 |
| 数据导入 | CSV/Excel 导入 | 先支持人工/半自动数据进入系统 |
| 数据源适配 | 采集器接口抽象 | 为后续蒲公英/第三方 API 接入预留 |
| 数据校验 | 字段校验、缺失标记、异常值标记 | 不把缺失数据当作健康数据 |
| 评分引擎 | 四维度评分、扣分原因、置信度 | 使用统一指标口径 |
| 评分查询 | 最新评分、历史评分、评分明细 | REST API + 基础页面 |
| 看板 | 账号列表、详情页、趋势图 | 先做运营可用，不追求复杂 BI |
| 告警 | 评分跌破阈值、互动率骤降、长期停更 | 站内列表为主，通知通道可后置 |

### 2.2 MVP 暂不做

| 暂缓项 | 后置原因 |
|------|------|
| Airflow 调度平台 | MVP 可先用定时任务或手动触发，降低部署复杂度 |
| ClickHouse 数仓 | 早期数据量可由 PostgreSQL 支撑 |
| MinIO/OSS 报告归档 | 先不做批量 PDF/Excel 报告 |
| Prometheus/Grafana 全量监控 | 先保留健康检查和应用日志 |
| 多第三方平台自动采集 | 先完成接口验真和字段映射 |
| 复杂模型训练 | 先使用规则模型，积累样本后校准 |

---

## 3. MVP 架构

```text
Vue3 管理端
    |
FastAPI API 服务
    |
PostgreSQL
    |-- 账号主数据
    |-- 每日账号快照
    |-- 每日笔记指标
    |-- 评分结果
    |-- 告警记录

可选：
Redis 用于缓存最新评分、任务锁和告警冷却。
```

MVP 阶段建议只部署：

- `FastAPI`
- `Vue3`
- `PostgreSQL`
- `Redis` 可选
- `Nginx` 可选

不建议一开始就引入 `Airflow + ClickHouse + MinIO + Prometheus + Grafana` 的完整组合。

---

## 4. 数据源验真

在正式接入蒲公英或第三方平台前，必须先完成接口验真表。

| 验真项 | 内容 | 状态 |
|------|------|------|
| 数据平台 | 蒲公英 / 新红 / 蝉妈妈 / 飞瓜 | 待确认 |
| 接口名称 | 实际接口名称与路径 | 待确认 |
| 授权方式 | OAuth / API Key / 后台导出 | 待确认 |
| 授权主体 | MCN / 品牌方 / 博主本人 | 待确认 |
| 是否需要博主授权 | 是 / 否 | 待确认 |
| 可用字段 | 粉丝、阅读、互动、画像、合作报价等 | 待确认 |
| 调用频率 | 每小时/每日额度 | 待确认 |
| 历史数据范围 | 可回溯天数 | 待确认 |
| 商用限制 | 是否允许用于评分和投放决策 | 待确认 |
| 失败降级 | 手动导入 / 缓存 / 跳过评分 | 待确认 |

验真完成前，MVP 使用 CSV/Excel 导入或模拟适配器跑通评分闭环。

---

## 5. 指标口径规范

所有比率类字段在数据库和代码中统一使用小数，展示层再转为百分比。

| 指标 | 存储口径 | 展示示例 | 说明 |
|------|------|------|------|
| 粉丝增长率 | `0.05` | `5%` | `(当前粉丝 - 上期粉丝) / 上期粉丝` |
| 互动率 | `0.035` | `3.5%` | `(点赞+收藏+评论+分享) / 阅读量` |
| 收藏率 | `0.05` | `5%` | `收藏数 / 阅读量` |
| 评论率 | `0.005` | `0.5%` | `评论数 / 阅读量` |
| CQI | `0.052` | `5.2%` | 加权互动指标 / 阅读量 |
| 广告标注合规率 | `1.0` | `100%` | 已正确标注广告笔记 / 合作笔记 |
| 审核通过率 | `0.95` | `95%` | 首次审核通过笔记 / 总笔记 |

关键规则：

- 不允许同一字段一处用 `5` 表示 `5%`，另一处用 `0.05` 表示 `5%`。
- 缺失值使用 `null`，不能默认写成健康值。
- 指标计算必须记录 `source`、`data_date`、`calculated_at`。
- 所有时间字段使用带时区时间，业务展示默认 `Asia/Shanghai`。

---

## 6. 数据完整度与置信度

评分结果必须同时输出健康分和置信度。健康分回答“当前看起来是否健康”，置信度回答“这个结论有多可靠”。

### 6.1 数据完整度

```text
data_completeness = 已获得关键字段数 / 应获得关键字段数
```

MVP 关键字段建议：

| 维度 | 必需字段 |
|------|------|
| 数据指标 | 粉丝数、粉丝增量、阅读量、点赞、收藏、评论、分享、发布数 |
| 内容质量 | 笔记数、阅读量、互动数据、标签或分类、原创标记 |
| 合规风险 | 违规记录、广告标注、审核状态 |
| 转化能力 | 报价、平均互动、粉丝画像、合作笔记表现 |

### 6.2 置信度等级

| 等级 | 条件 | 处理方式 |
|------|------|------|
| High | 完整度 `>= 0.85` 且关键字段无缺失 | 正常展示评分 |
| Medium | 完整度 `>= 0.60` | 展示评分，但提示部分数据缺失 |
| Low | 完整度 `< 0.60` 或核心字段缺失 | 不建议用于投放决策 |

### 6.3 缺失数据处理

- 缺合规数据时，不默认合规满分，应标记为 `unknown`。
- 缺转化数据时，转化维度可不参与总分，权重按已知维度重新归一化。
- 缺阅读量时，互动率、收藏率、评论率、CQI 不计算。
- 缺历史数据时，不触发趋势类告警。

---

## 7. MVP 数据模型补充

原方案中的 `accounts`、`notes`、`scores` 可以保留，但建议补充以下表或字段。

### 7.1 账号每日快照

```sql
CREATE TABLE account_daily_snapshots (
    id BIGSERIAL PRIMARY KEY,
    account_id BIGINT NOT NULL REFERENCES accounts(id),
    data_date DATE NOT NULL,
    fans_count INTEGER,
    fans_delta INTEGER,
    notes_count INTEGER,
    total_reads BIGINT,
    total_likes BIGINT,
    total_collects BIGINT,
    total_comments BIGINT,
    total_shares BIGINT,
    publish_count INTEGER,
    data_source VARCHAR(64),
    raw_payload JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(account_id, data_date, data_source)
);
```

### 7.2 笔记每日指标

```sql
CREATE TABLE note_daily_metrics (
    id BIGSERIAL PRIMARY KEY,
    note_id VARCHAR(64) NOT NULL,
    account_id BIGINT NOT NULL REFERENCES accounts(id),
    data_date DATE NOT NULL,
    read_count INTEGER,
    like_count INTEGER,
    collect_count INTEGER,
    comment_count INTEGER,
    share_count INTEGER,
    interaction_rate DECIMAL(8,6),
    cqi DECIMAL(8,6),
    data_source VARCHAR(64),
    raw_payload JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(note_id, data_date, data_source)
);
```

### 7.3 评分结果补充字段

```sql
ALTER TABLE scores
ADD COLUMN model_version VARCHAR(32) DEFAULT 'rules_v1',
ADD COLUMN data_completeness DECIMAL(5,4),
ADD COLUMN confidence_level VARCHAR(16),
ADD COLUMN missing_fields JSONB DEFAULT '[]',
ADD COLUMN warning_flags JSONB DEFAULT '[]';
```

---

## 8. MVP 评分规则

### 8.1 总分计算

```text
HealthScore = Σ(可用维度权重 × 维度最终分)
```

当某个维度数据不足时：

1. 该维度标记为 `unknown`。
2. 总分只用可用维度计算。
3. 输出 `confidence_level`，提示不可直接用于高风险决策。

### 8.2 建议默认权重

| 场景 | 数据指标 | 内容质量 | 合规风险 | 转化能力 |
|------|------|------|------|------|
| 通用 MVP | 0.35 | 0.30 | 0.25 | 0.10 |
| 品牌投放 MVP | 0.25 | 0.25 | 0.35 | 0.15 |
| MCN 管理 MVP | 0.40 | 0.30 | 0.20 | 0.10 |

MVP 阶段转化能力通常数据不完整，因此权重不宜过高。

### 8.3 输出结构

每次评分至少输出：

- `total_score`
- `health_level`
- `dimensions`
- `indicator_scores`
- `penalty_reasons`
- `suggestions`
- `data_completeness`
- `confidence_level`
- `missing_fields`
- `model_version`

---

## 9. API 范围

| 方法 | 路径 | MVP 说明 |
|------|------|------|
| `POST` | `/api/v1/accounts` | 添加账号 |
| `GET` | `/api/v1/accounts` | 账号列表 |
| `POST` | `/api/v1/imports/accounts` | 导入账号和指标数据 |
| `POST` | `/api/v1/scores/trigger` | 手动触发评分 |
| `GET` | `/api/v1/scores/{account_id}` | 最新评分 |
| `GET` | `/api/v1/scores/{account_id}/history` | 历史评分 |
| `GET` | `/api/v1/alerts` | 告警列表 |
| `GET` | `/api/v1/health` | 健康检查 |

批量报告、文件下载、多通知通道可以放到生产演进阶段。

---

## 10. 看板范围

MVP 看板只做高频工作流：

1. 账号列表：昵称、赛道、粉丝、最新评分、等级、置信度、更新时间。
2. 账号详情：总分、四维度分、扣分原因、缺失字段、近 30 天趋势。
3. 告警列表：严重级别、账号、指标、当前值、触发时间、处理状态。
4. 数据导入页：上传文件、校验结果、错误行下载。

---

## 11. 验收标准

| 验收项 | 标准 |
|------|------|
| 数据导入 | 可以导入 100 个账号、近 30 天指标数据 |
| 评分计算 | 单账号评分耗时 `< 1s` |
| 批量评分 | 100 个账号评分耗时 `< 30s` |
| 可解释性 | 每个低分维度至少有一个原因或缺失提示 |
| 置信度 | 缺关键字段时能正确降级 |
| 历史趋势 | 可以查看账号近 30 天评分变化 |
| 告警 | 评分低于阈值、互动率骤降、长期未更新能触发记录 |

---

## 12. 4-6 周排期

| 阶段 | 周期 | 交付物 |
|------|------|------|
| 第 1 周 | 项目骨架、数据库、导入模板、基础账号管理 | 可创建账号并导入数据 |
| 第 2 周 | 数据校验、快照表、笔记每日指标表 | 数据可沉淀并追踪历史 |
| 第 3 周 | 评分引擎、口径统一、置信度输出 | 可计算健康分 |
| 第 4 周 | 评分 API、账号列表、详情页 | 用户可查看评分和原因 |
| 第 5 周 | 告警、趋势、导入错误处理 | 内测可用 |
| 第 6 周 | 回测、样本校准、部署脚本 | MVP 交付 |

---

## 13. MVP 后进入生产化的条件

满足以下条件后，再进入生产演进：

- 至少完成 200 个账号样本回测。
- 至少覆盖 3 个主要赛道。
- 评分结果经业务人工复核，明显误判率可接受。
- 数据源接口验真完成。
- 缺失数据和低置信度场景已有明确提示。
- 账号授权和数据使用边界已确认。
