from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from xhs_health.auth import build_auth_middleware
from xhs_health.config import _positive_int_env
from xhs_health.main import app


def test_import_and_score_flow() -> None:
    platform_uid = f"uid_{uuid4().hex}"
    payload = {
        "accounts": [
            {
                "platform_uid": platform_uid,
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
                        "data_source": "manual",
                    }
                ],
                "notes": [
                    {
                        "note_id": f"note_{uuid4().hex}",
                        "title": "夏季护肤清单",
                        "content_type": "image",
                        "publish_time": "2026-06-19T10:00:00+08:00",
                        "is_ad": False,
                        "is_original": True,
                        "tags": ["护肤", "夏季"],
                        "metrics": [
                            {
                                "data_date": "2026-06-19",
                                "read_count": 30000,
                                "like_count": 1800,
                                "collect_count": 1200,
                                "comment_count": 180,
                                "share_count": 70,
                                "data_source": "manual",
                            }
                        ],
                    }
                ],
            }
        ]
    }

    with TestClient(app) as client:
        assert client.get("/api/v1/health").json() == {"status": "ok"}

        imported = client.post("/api/v1/imports/accounts", json=payload)
        assert imported.status_code == 200
        assert imported.json()["accounts_upserted"] == 1

        accounts = client.get("/api/v1/accounts")
        assert accounts.status_code == 200
        account_id = next(item["id"] for item in accounts.json() if item["platform_uid"] == platform_uid)

        score = client.post("/api/v1/scores/trigger", json={"account_id": account_id})
        assert score.status_code == 200
        body = score.json()
        assert body["account_id"] == account_id
        assert body["confidence_level"] == "High"
        assert body["total_score"] > 0

        latest = client.get(f"/api/v1/scores/{account_id}")
        assert latest.status_code == 200
        assert latest.json()["id"] == body["id"]

        batch = client.post("/api/v1/scores/batch-trigger", json={"account_ids": [account_id]})
        assert batch.status_code == 200
        assert batch.json()[0]["account_id"] == account_id

        empty = client.post(
            "/api/v1/accounts",
            json={"platform_uid": f"empty_{platform_uid}", "nickname": "空数据账号"},
        )
        assert empty.status_code == 200
        mixed_batch = client.post(
            "/api/v1/scores/batch-trigger",
            json={"account_ids": [account_id, empty.json()["id"]]},
        )
        assert mixed_batch.status_code == 200
        assert [item["account_id"] for item in mixed_batch.json()] == [account_id]

        overview = client.get("/api/v1/stats/overview")
        assert overview.status_code == 200
        assert overview.json()["monitored_accounts"] >= 1


def test_auth_middleware_protects_private_routes() -> None:
    from fastapi import FastAPI

    protected_app = FastAPI()
    protected_app.middleware("http")(build_auth_middleware("/api/v1", "test-token"))

    @protected_app.get("/api/v1/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @protected_app.get("/api/v1/private")
    def private() -> dict[str, bool]:
        return {"ok": True}

    with TestClient(protected_app) as client:
        assert client.get("/api/v1/health").status_code == 200
        unauthorized = client.get("/api/v1/private")
        assert unauthorized.status_code == 401
        assert unauthorized.headers["www-authenticate"] == "Bearer"
        authorized = client.get(
            "/api/v1/private", headers={"Authorization": "Bearer test-token"}
        )
        assert authorized.status_code == 200


def test_scheduler_interval_must_be_positive(monkeypatch) -> None:
    monkeypatch.setenv("SCHEDULER_INTERVAL_SECONDS", "30")
    with pytest.raises(ValueError, match="must be at least 60"):
        _positive_int_env("SCHEDULER_INTERVAL_SECONDS", 3600, minimum=60)
    monkeypatch.setenv("SCHEDULER_INTERVAL_SECONDS", "abc")
    with pytest.raises(ValueError, match="must be an integer"):
        _positive_int_env("SCHEDULER_INTERVAL_SECONDS", 3600, minimum=60)


def test_csv_file_import() -> None:
    platform_uid = f"uid_{uuid4().hex}"
    csv_body = (
        "platform_uid,nickname,category,data_date,fans_count,fans_delta,notes_count,"
        "total_reads,total_likes,total_collects,total_comments,total_shares,publish_count,"
        "violation_count_180d,ad_compliance_rate,audit_pass_rate,shadowban_risk,"
        "fan_quality_score,cpe,avg_cpe_benchmark,business_stability\n"
        f"{platform_uid},CSV博主,家居,2026-06-19,12000,120,30,"
        "50000,1800,900,160,80,1,"
        "0,1,0.99,0.02,0.7,2.5,3.1,0.8\n"
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/imports/account-metrics-file",
            files={"file": ("sample.csv", csv_body.encode("utf-8"), "text/csv")},
        )
        assert response.status_code == 200
        assert response.json()["accounts_upserted"] == 1

        account_id = next(
            item["id"]
            for item in client.get("/api/v1/accounts").json()
            if item["platform_uid"] == platform_uid
        )
        score = client.post("/api/v1/scores/trigger", json={"account_id": account_id})
        assert score.status_code == 200
        assert score.json()["total_score"] > 0


def test_import_template_download() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/imports/template")
        assert response.status_code == 200
        assert "platform_uid,nickname,category" in response.text
        assert "attachment" in response.headers["content-disposition"]


def test_resolve_alert() -> None:
    platform_uid = f"alert_{uuid4().hex}"
    payload = {
        "accounts": [
            {
                "platform_uid": platform_uid,
                "nickname": "低分账号",
                "snapshots": [
                    {
                        "data_date": "2026-06-19",
                        "fans_count": 100,
                        "fans_delta": -20,
                        "total_reads": 1000,
                        "total_likes": 1,
                        "total_collects": 1,
                        "total_comments": 0,
                        "total_shares": 0,
                        "publish_count": 0,
                    }
                ],
            }
        ]
    }
    with TestClient(app) as client:
        imported = client.post("/api/v1/imports/accounts", json=payload)
        assert imported.status_code == 200
        account_id = next(
            item["id"]
            for item in client.get("/api/v1/accounts").json()
            if item["platform_uid"] == platform_uid
        )
        assert client.post("/api/v1/scores/trigger", json={"account_id": account_id}).status_code == 200
        alert = next(item for item in client.get("/api/v1/alerts").json() if item["account_id"] == account_id)
        resolved = client.put(f"/api/v1/alerts/{alert['id']}/resolve")
        assert resolved.status_code == 200
        assert resolved.json()["is_resolved"] is True


def test_account_status_update_filter_and_archive() -> None:
    platform_uid = f"status_{uuid4().hex}"

    with TestClient(app) as client:
        created = client.post(
            "/api/v1/accounts",
            json={"platform_uid": platform_uid, "nickname": "Status Account", "category": "ops"},
        )
        assert created.status_code == 200
        account_id = created.json()["id"]
        assert created.json()["status"] == "active"

        paused = client.put(f"/api/v1/accounts/{account_id}", json={"status": "paused"})
        assert paused.status_code == 200
        assert paused.json()["status"] == "paused"

        paused_accounts = client.get("/api/v1/accounts?status=paused")
        assert paused_accounts.status_code == 200
        assert any(item["id"] == account_id for item in paused_accounts.json())

        archived = client.delete(f"/api/v1/accounts/{account_id}")
        assert archived.status_code == 200
        assert archived.json()["status"] == "archived"

        active_accounts = client.get("/api/v1/accounts?status=active")
        assert active_accounts.status_code == 200
        assert all(item["id"] != account_id for item in active_accounts.json())


def test_groups_import_errors_alert_rules_and_sources() -> None:
    suffix = uuid4().hex

    with TestClient(app) as client:
        account = client.post(
            "/api/v1/accounts",
            json={"platform_uid": f"group_{suffix}", "nickname": "Grouped Account"},
        )
        assert account.status_code == 200
        account_id = account.json()["id"]

        group = client.post("/api/v1/groups", json={"name": f"Group {suffix}"})
        assert group.status_code == 200
        group_id = group.json()["id"]

        members = client.put(f"/api/v1/groups/{group_id}/members", json={"account_ids": [account_id]})
        assert members.status_code == 200
        assert members.json()["account_ids"] == [account_id]

        filtered = client.get(f"/api/v1/accounts?group_id={group_id}")
        assert filtered.status_code == 200
        assert any(item["id"] == account_id and group_id in item["group_ids"] for item in filtered.json())

        csv_body = (
            "platform_uid,nickname,data_date,fans_count\n"
            f"bad_{suffix},Bad Date,not-a-date,100\n"
            f"good_{suffix},Good Row,2026-06-19,100\n"
        )
        imported = client.post(
            "/api/v1/imports/account-metrics-file",
            files={"file": ("bad.csv", csv_body.encode("utf-8"), "text/csv")},
        )
        assert imported.status_code == 200
        body = imported.json()
        assert body["accounts_upserted"] == 1
        assert body["error_rows"] == 1

        errors = client.get(f"/api/v1/imports/batches/{body['import_batch_id']}/errors")
        assert errors.status_code == 200
        assert errors.json()[0]["field_name"] == "data_date"

        errors_csv = client.get(f"/api/v1/imports/batches/{body['import_batch_id']}/errors.csv")
        assert errors_csv.status_code == 200
        assert "not-a-date" in errors_csv.text

        rule = client.post(
            "/api/v1/alerts/rules",
            json={
                "name": f"Any score {suffix}",
                "alert_type": f"custom_{suffix}",
                "metric_name": "total_score",
                "operator": "gt",
                "threshold_value": 0,
                "severity": "warning",
                "enabled": True,
                "cooldown_minutes": 1440,
            },
        )
        assert rule.status_code == 200

        source = client.post(
            "/api/v1/data-sources/verifications",
            json={
                "source": f"pgy_{suffix}",
                "interface_name": "creator.profile",
                "status": "pending",
                "available_fields": ["fans_count"],
            },
        )
        assert source.status_code == 200
        listed_sources = client.get("/api/v1/data-sources/verifications")
        assert listed_sources.status_code == 200
        assert any(item["source"] == f"pgy_{suffix}" for item in listed_sources.json())


def test_builtin_alerts_cover_mvp_conditions() -> None:
    platform_uid = f"alert_rules_{uuid4().hex}"
    payload = {
        "accounts": [
            {
                "platform_uid": platform_uid,
                "nickname": "Alert Rule Account",
                "violation_count_180d": 0,
                "ad_compliance_rate": 1.0,
                "audit_pass_rate": 0.99,
                "shadowban_risk": 0.4,
                "snapshots": [
                    {
                        "data_date": "2026-06-18",
                        "fans_count": 10000,
                        "fans_delta": 100,
                        "total_reads": 10000,
                        "total_likes": 500,
                        "total_collects": 300,
                        "total_comments": 100,
                        "total_shares": 100,
                        "publish_count": 1,
                    },
                    {
                        "data_date": "2026-06-19",
                        "fans_count": 9700,
                        "fans_delta": -300,
                        "total_reads": 10000,
                        "total_likes": 10,
                        "total_collects": 10,
                        "total_comments": 5,
                        "total_shares": 5,
                        "publish_count": 0,
                    },
                ],
            }
        ]
    }

    with TestClient(app) as client:
        imported = client.post("/api/v1/imports/accounts", json=payload)
        assert imported.status_code == 200
        account_id = next(
            item["id"]
            for item in client.get("/api/v1/accounts").json()
            if item["platform_uid"] == platform_uid
        )
        score = client.post("/api/v1/scores/trigger", json={"account_id": account_id})
        assert score.status_code == 200
        alert_types = {
            item["alert_type"]
            for item in client.get("/api/v1/alerts").json()
            if item["account_id"] == account_id
        }
        assert "interaction_drop" in alert_types
        assert "fan_loss" in alert_types
        assert "shadowban_risk" in alert_types


def test_authorization_export_anonymize_and_audit_flow() -> None:
    suffix = uuid4().hex

    with TestClient(app) as client:
        account = client.post(
            "/api/v1/accounts",
            json={"platform_uid": f"auth_{suffix}", "nickname": "Authorized Account"},
        )
        assert account.status_code == 200
        account_id = account.json()["id"]

        authorization = client.post(
            f"/api/v1/authorizations/accounts/{account_id}",
            json={
                "authorization_type": "contract",
                "authorized_by": "tester",
                "scope": {"metrics": True, "notes": True},
                "proof_url": "https://example.com/proof",
            },
        )
        assert authorization.status_code == 200
        authorization_id = authorization.json()["id"]

        exported = client.get(f"/api/v1/authorizations/accounts/{account_id}/export")
        assert exported.status_code == 200
        exported_body = exported.json()
        assert exported_body["account"]["id"] == account_id
        assert exported_body["authorizations"][0]["id"] == authorization_id

        revoked = client.put(f"/api/v1/authorizations/{authorization_id}/revoke?actor=tester")
        assert revoked.status_code == 200
        assert revoked.json()["revoked_at"] is not None
        assert client.get(f"/api/v1/accounts/{account_id}").json()["status"] == "archived"

        anonymized = client.post(
            f"/api/v1/authorizations/accounts/{account_id}/data-deletion",
            json={"mode": "anonymize", "actor": "tester", "reason": "user request"},
        )
        assert anonymized.status_code == 200
        assert anonymized.json()["action"] == "anonymize"
        assert client.get(f"/api/v1/accounts/{account_id}").json()["nickname"] == "Anonymized Account"

        logs = client.get("/api/v1/audit-logs")
        assert logs.status_code == 200
        actions = {item["action"] for item in logs.json()}
        assert "authorization.created" in actions
        assert "authorization.revoked" in actions
        assert "account_data.anonymized" in actions


def test_notification_channel_test_delivery() -> None:
    suffix = uuid4().hex

    with TestClient(app) as client:
        channel = client.post(
            "/api/v1/notifications/channels",
            json={
                "name": f"Ops Webhook {suffix}",
                "channel_type": "webhook",
                "target": "https://example.com/webhook",
                "enabled": True,
            },
        )
        assert channel.status_code == 200
        channel_id = channel.json()["id"]

        delivery = client.post(
            f"/api/v1/notifications/channels/{channel_id}/test",
            json={"event_type": "health_alert", "dry_run": True, "payload": {"score": 42}},
        )
        assert delivery.status_code == 200
        assert delivery.json()["status"] == "dry_run"
        assert delivery.json()["payload"]["payload"]["score"] == 42

        deliveries = client.get("/api/v1/notifications/deliveries")
        assert deliveries.status_code == 200
        assert any(item["id"] == delivery.json()["id"] for item in deliveries.json())


def test_reports_xlsx_and_single_account_json() -> None:
    platform_uid = f"report_{uuid4().hex}"

    with TestClient(app) as client:
        imported = client.post(
            "/api/v1/imports/accounts",
            json={
                "accounts": [
                    {
                        "platform_uid": platform_uid,
                        "nickname": "Report Account",
                        "fan_quality_score": 0.8,
                        "snapshots": [{"data_date": "2026-06-19", "fans_count": 1000}],
                    }
                ]
            },
        )
        assert imported.status_code == 200
        account_id = next(
            item["id"]
            for item in client.get("/api/v1/accounts").json()
            if item["platform_uid"] == platform_uid
        )
        assert client.post("/api/v1/scores/trigger", json={"account_id": account_id}).status_code == 200

        xlsx = client.get("/api/v1/reports/accounts.xlsx")
        assert xlsx.status_code == 200
        assert xlsx.content.startswith(b"PK")

        single = client.get(f"/api/v1/reports/accounts/{account_id}.json")
        assert single.status_code == 200
        body = single.json()
        assert body["account"]["id"] == account_id
        assert body["latest_score"]["account_id"] == account_id
        assert "suggestions" in body["summary"]


def test_accounts_pagination() -> None:
    prefix = f"page_{uuid4().hex}"
    accounts_in = [
        {"platform_uid": f"{prefix}_{i}", "nickname": f"Page Account {i}"}
        for i in range(3)
    ]

    with TestClient(app) as client:
        imported = client.post("/api/v1/imports/accounts", json={"accounts": accounts_in})
        assert imported.status_code == 200

        first = client.get("/api/v1/accounts?status=active&limit=2&offset=0")
        assert first.status_code == 200
        first_body = first.json()
        assert len(first_body) <= 2
        assert first.headers.get("x-total-count") is not None
        total = int(first.headers["x-total-count"])
        assert total >= 3

        second = client.get("/api/v1/accounts?status=active&limit=2&offset=2")
        assert second.status_code == 200
        second_body = second.json()
        assert int(second.headers["x-total-count"]) == total

        first_ids = {item["id"] for item in first_body}
        second_ids = {item["id"] for item in second_body}
        assert first_ids.isdisjoint(second_ids)


def test_csv_business_rule_violation_recorded_as_error() -> None:
    """A row that passes _validate_row type checks but fails business rules
    (e.g. ratio out of [0,1]) must be recorded as an ImportErrorRow and counted
    in error_rows, not silently dropped."""
    suffix = uuid4().hex
    csv_body = (
        "platform_uid,nickname,data_date,fans_count,ad_compliance_rate\n"
        f"bad_ratio_{suffix},Bad Ratio,2026-06-19,100,1.5\n"
        f"good_{suffix},Good Row,2026-06-19,100,0.95\n"
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/imports/account-metrics-file",
            files={"file": ("bad_ratio.csv", csv_body.encode("utf-8"), "text/csv")},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["accounts_upserted"] == 1
        assert body["error_rows"] == 1
        assert body["total_rows"] == 2

        errors = client.get(f"/api/v1/imports/batches/{body['import_batch_id']}/errors")
        assert errors.status_code == 200
        assert any(
            err["field_name"] == "ad_compliance_rate" for err in errors.json()
        ), errors.json()



def _account_payload(platform_uid: str, note_id: str, note_date: str) -> dict:
    return {
        "platform_uid": platform_uid,
        "nickname": "审计测试博主",
        "snapshots": [
            {
                "data_date": "2026-06-19",
                "fans_count": 12000,
                "fans_delta": 120,
                "total_reads": 50000,
                "total_likes": 1800,
                "total_collects": 900,
                "total_comments": 160,
                "total_shares": 80,
                "publish_count": 1,
            }
        ],
        "notes": [
            {
                "note_id": note_id,
                "title": "测试笔记",
                "publish_time": f"{note_date}T10:00:00+08:00",
                "is_ad": False,
                "is_original": True,
                "tags": ["测试"],
                "metrics": [
                    {
                        "data_date": note_date,
                        "read_count": 8000,
                        "like_count": 500,
                        "collect_count": 200,
                        "comment_count": 50,
                        "share_count": 20,
                    }
                ],
            }
        ],
    }


def test_note_import_conflict_recorded_in_batch() -> None:
    """A note_id already owned by another account must be rejected with an
    ImportErrorRow instead of silently reassigning its owner."""
    from sqlalchemy import select as sa_select

    from xhs_health.db import SessionLocal
    from xhs_health.models import Note as NoteModel

    shared_note = f"note_{uuid4().hex}"
    uid_a, uid_b = f"uid_{uuid4().hex}", f"uid_{uuid4().hex}"

    with TestClient(app) as client:
        first = client.post(
            "/api/v1/imports/accounts",
            json={"accounts": [_account_payload(uid_a, shared_note, "2026-06-19")]},
        )
        assert first.status_code == 200
        assert first.json()["error_rows"] == 0

        second = client.post(
            "/api/v1/imports/accounts",
            json={"accounts": [_account_payload(uid_b, shared_note, "2026-06-19")]},
        )
        assert second.status_code == 200
        assert second.json()["error_rows"] == 1

        batch_id = second.json()["import_batch_id"]
        errors = client.get(f"/api/v1/imports/batches/{batch_id}/errors")
        conflict = next(err for err in errors.json() if err["field_name"] == "note_id")
        assert conflict["row_number"] == 1
        assert shared_note in conflict["message"]

        account_a = next(
            item for item in client.get("/api/v1/accounts").json() if item["platform_uid"] == uid_a
        )
        session = SessionLocal()
        try:
            note = session.scalar(sa_select(NoteModel).where(NoteModel.note_id == shared_note))
            assert note is not None
            assert note.account_id == account_a["id"]
        finally:
            session.close()


def test_json_import_error_row_numbering_starts_at_one() -> None:
    payload = _account_payload(f"uid_{uuid4().hex}", f"note_{uuid4().hex}", "2026-06-19")
    payload["ad_compliance_rate"] = 1.5  # business-rule failure on the first account

    with TestClient(app) as client:
        imported = client.post("/api/v1/imports/accounts", json={"accounts": [payload]})
        assert imported.status_code == 200
        assert imported.json()["error_rows"] == 1

        errors = client.get(f"/api/v1/imports/batches/{imported.json()['import_batch_id']}/errors")
        assert errors.json()[0]["row_number"] == 1


def test_stale_notes_excluded_from_scoring() -> None:
    """Notes whose metrics/publish date fall outside the analysis window must
    not feed the content dimension."""
    platform_uid = f"stale_{uuid4().hex}"
    payload = _account_payload(platform_uid, f"note_{uuid4().hex}", "2026-01-01")

    with TestClient(app) as client:
        imported = client.post("/api/v1/imports/accounts", json={"accounts": [payload]})
        assert imported.status_code == 200

        account_id = next(
            item["id"]
            for item in client.get("/api/v1/accounts").json()
            if item["platform_uid"] == platform_uid
        )
        score = client.post("/api/v1/scores/trigger", json={"account_id": account_id})
        assert score.status_code == 200
        assert score.json()["content_score"] is None
        assert "notes" in score.json()["missing_fields"]


def test_alert_thresholds_configurable() -> None:
    """Alert cut-offs come from ScoreThresholds, so callers can tune them."""
    from datetime import date

    from sqlalchemy import select as sa_select

    from xhs_health.db import SessionLocal
    from xhs_health.models import Account as AccountModel
    from xhs_health.models import Alert as AlertModel
    from xhs_health.models import AccountDailySnapshot as SnapshotModel
    from xhs_health.services.score_service import calculate_and_store_score
    from xhs_health.services.scoring import ScoreThresholds

    platform_uid = f"th_{uuid4().hex}"
    with TestClient(app):  # ensures init_db has run
        session = SessionLocal()
        try:
            account = AccountModel(platform_uid=platform_uid, nickname="阈值测试")
            session.add(account)
            session.flush()
            session.add(
                SnapshotModel(
                    account_id=account.id,
                    data_date=date(2026, 6, 19),
                    fans_count=52000,
                    fans_delta=320,
                    total_reads=180000,
                    total_likes=8200,
                    total_collects=5100,
                    total_comments=920,
                    total_shares=310,
                    publish_count=1,
                    data_source="manual",
                )
            )
            session.commit()

            calculate_and_store_score(session, account.id)
            session.commit()
            default_alerts = session.scalars(
                sa_select(AlertModel).where(
                    AlertModel.account_id == account.id,
                    AlertModel.alert_type == "low_score",
                )
            ).all()
            assert default_alerts == []

            calculate_and_store_score(
                session, account.id, thresholds=ScoreThresholds(alert_low_score=200.0)
            )
            session.commit()
            tuned = session.scalars(
                sa_select(AlertModel).where(
                    AlertModel.account_id == account.id,
                    AlertModel.alert_type == "low_score",
                )
            ).all()
            assert len(tuned) == 1
            assert float(tuned[0].threshold_value) == 200.0
        finally:
            session.close()


def test_alerts_pagination_and_filters() -> None:
    platform_uid = f"pag_{uuid4().hex}"
    payload = {
        "accounts": [
            {
                "platform_uid": platform_uid,
                "nickname": "分页测试账号",
                "snapshots": [
                    {
                        "data_date": "2026-06-19",
                        "fans_count": 100,
                        "fans_delta": -20,
                        "total_reads": 1000,
                        "total_likes": 1,
                        "total_collects": 1,
                        "total_comments": 0,
                        "total_shares": 0,
                        "publish_count": 0,
                    }
                ],
            }
        ]
    }

    with TestClient(app) as client:
        imported = client.post("/api/v1/imports/accounts", json=payload)
        assert imported.status_code == 200
        account_id = next(
            item["id"]
            for item in client.get("/api/v1/accounts").json()
            if item["platform_uid"] == platform_uid
        )
        assert client.post("/api/v1/scores/trigger", json={"account_id": account_id}).status_code == 200

        scoped = client.get(f"/api/v1/alerts?account_id={account_id}")
        total = int(scoped.headers["X-Total-Count"])
        assert total >= 2

        low_confidence = next(
            a for a in scoped.json() if a["alert_type"] == "low_confidence"
        )
        assert low_confidence["threshold_value"] == 0.6

        first = client.get(f"/api/v1/alerts?account_id={account_id}&limit=1")
        assert len(first.json()) == 1
        assert first.headers["X-Total-Count"] == str(total)
        second = client.get(f"/api/v1/alerts?account_id={account_id}&limit=1&offset=1")
        assert len(second.json()) == 1
        assert second.json()[0]["id"] != first.json()[0]["id"]

        unresolved = client.get(
            f"/api/v1/alerts?account_id={account_id}&unresolved_only=true&limit=500"
        )
        assert all(a["is_resolved"] is False for a in unresolved.json())
        assert len(unresolved.json()) == total

        assert (
            client.put(f"/api/v1/alerts/{first.json()[0]['id']}/resolve").status_code == 200
        )
        after = client.get(
            f"/api/v1/alerts?account_id={account_id}&unresolved_only=true&limit=500"
        )
        assert int(after.headers["X-Total-Count"]) == total - 1


def test_negative_counters_rejected() -> None:
    """Cumulative counters (reads/likes/...) must be non-negative; fans_delta
    stays signed because losing fans is legitimate."""
    suffix = uuid4().hex
    csv_body = (
        "platform_uid,nickname,data_date,fans_count,total_reads,note_id,read_count\n"
        f"neg_{suffix},负数计数,2026-06-19,100,-5,,\n"
        f"neg_{suffix},负数计数,2026-06-19,100,1000,bad_note_{suffix},-3\n"
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/imports/account-metrics-file",
            files={"file": ("negative.csv", csv_body.encode("utf-8"), "text/csv")},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["accounts_upserted"] == 0
        assert body["error_rows"] == 1

        errors = client.get(f"/api/v1/imports/batches/{body['import_batch_id']}/errors")
        fields = {err["field_name"] for err in errors.json()}
        assert "total_reads" in fields
        assert "read_count" in fields


def test_overview_uses_latest_score_by_date() -> None:
    """A backfilled historical score (larger id, older date) must not change the
    account's classification in overview stats."""
    from datetime import date

    from xhs_health.db import SessionLocal
    from xhs_health.models import Account as AccountModel
    from xhs_health.models import Score as ScoreModel

    platform_uid = f"ov_{uuid4().hex}"
    with TestClient(app) as client:
        session = SessionLocal()
        try:
            account = AccountModel(platform_uid=platform_uid, nickname="口径测试")
            session.add(account)
            session.flush()
            session.add(
                ScoreModel(
                    account_id=account.id,
                    score_date=date(2026, 6, 19),
                    total_score=80,
                    health_level="B",
                )
            )
            session.commit()
        finally:
            session.close()

        before = client.get("/api/v1/stats/overview").json()

        from sqlalchemy import select as sa_select

        session = SessionLocal()
        try:
            account = session.scalar(
                sa_select(AccountModel).where(AccountModel.platform_uid == platform_uid)
            )
            session.add(
                ScoreModel(
                    account_id=account.id,
                    score_date=date(2026, 6, 10),  # backfilled: larger id, older date
                    total_score=30,
                    health_level="D",
                )
            )
            session.commit()
        finally:
            session.close()

        after = client.get("/api/v1/stats/overview").json()
        for key in ("healthy_accounts", "warning_accounts", "risky_accounts"):
            assert after[key] == before[key], key


def test_reports_export_latest_score_and_alerts() -> None:
    platform_uid = f"rpt_{uuid4().hex}"
    payload = {
        "accounts": [
            {
                "platform_uid": platform_uid,
                "nickname": "导出测试账号",
                "snapshots": [
                    {
                        "data_date": "2026-06-19",
                        "fans_count": 12000,
                        "fans_delta": 120,
                        "total_reads": 50000,
                        "total_likes": 1800,
                        "total_collects": 900,
                        "total_comments": 160,
                        "total_shares": 80,
                        "publish_count": 1,
                    }
                ],
            }
        ]
    }

    with TestClient(app) as client:
        imported = client.post("/api/v1/imports/accounts", json=payload)
        assert imported.status_code == 200
        account_id = next(
            item["id"]
            for item in client.get("/api/v1/accounts").json()
            if item["platform_uid"] == platform_uid
        )
        assert client.post("/api/v1/scores/trigger", json={"account_id": account_id}).status_code == 200

        report = client.get("/api/v1/reports/accounts.csv")
        assert report.status_code == 200
        header = report.text.splitlines()[0].split(",")
        row = next(line for line in report.text.splitlines()[1:] if f",{platform_uid}," in line)
        values = dict(zip(header, row.split(","), strict=False))
        assert values["platform_uid"] == platform_uid
        assert values["latest_score"] != ""
        assert values["health_level"] != ""
        assert int(values["unresolved_alerts"]) >= 0


def test_score_history_and_import_batches_limit() -> None:
    platform_uid = f"lim_{uuid4().hex}"
    payload = {
        "accounts": [
            {
                "platform_uid": platform_uid,
                "nickname": "限量测试账号",
                "snapshots": [
                    {
                        "data_date": "2026-06-19",
                        "fans_count": 12000,
                        "fans_delta": 120,
                        "total_reads": 50000,
                        "total_likes": 1800,
                        "total_collects": 900,
                        "total_comments": 160,
                        "total_shares": 80,
                        "publish_count": 1,
                    }
                ],
            }
        ]
    }

    with TestClient(app) as client:
        imported = client.post("/api/v1/imports/accounts", json=payload)
        assert imported.status_code == 200
        account_id = next(
            item["id"]
            for item in client.get("/api/v1/accounts").json()
            if item["platform_uid"] == platform_uid
        )
        assert client.post("/api/v1/scores/trigger", json={"account_id": account_id}).status_code == 200

        history = client.get(f"/api/v1/scores/{account_id}/history")
        assert history.status_code == 200
        assert len(history.json()) == 1

        capped = client.get(f"/api/v1/scores/{account_id}/history?limit=0")
        assert len(capped.json()) == 1  # clamped to minimum 1, not an error

        batches = client.get("/api/v1/imports/batches?limit=1")
        assert batches.status_code == 200
        assert len(batches.json()) == 1
        newest = batches.json()[0]
        assert newest["id"] == imported.json()["import_batch_id"]


# ---------- Adversarial regression tests ----------

def test_overflow_and_nan_values_rejected_not_500() -> None:
    """1e999 fans_count raised OverflowError (unhandled 500) and cpe=nan passed
    validation through to the DB; both must become error rows."""
    suffix = uuid4().hex
    csv_body = (
        "platform_uid,nickname,data_date,fans_count,cpe\n"
        f"ovf_{suffix},溢出,2026-06-19,1e999,2.1\n"
        f"nan_{suffix},非数,2026-06-19,100,nan\n"
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/imports/account-metrics-file",
            files={"file": ("adv.csv", csv_body.encode("utf-8"), "text/csv")},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["accounts_upserted"] == 0
        assert body["error_rows"] == 2

        errors = client.get(f"/api/v1/imports/batches/{body['import_batch_id']}/errors")
        messages = " | ".join(err["message"] for err in errors.json())
        assert "fans_count must be a finite number" in messages
        assert "cpe must be a finite number" in messages


def test_json_nan_cpe_rejected() -> None:
    import json
    """Python json accepts NaN tokens, so JSON imports can smuggle NaN past
    pydantic; validate_import_payload must reject it."""
    payload = {
        "platform_uid": f"nan_{uuid4().hex}",
        "nickname": "NaN注入",
        "cpe": None,  # placeholder; swapped to a raw NaN token below
        "snapshots": [
            {"data_date": "2026-06-19", "fans_count": 100, "fans_delta": 1}
        ],
    }

    with TestClient(app) as client:
        # Send the raw NaN token — server-side json.loads accepts it even though
        # httpx's json= helper refuses to encode NaN.
        imported = client.post(
            "/api/v1/imports/accounts",
            content=json.dumps({"accounts": [payload]}).replace('"cpe": null', '"cpe": NaN'),
            headers={"Content-Type": "application/json"},
        )
        assert imported.status_code == 200
        assert imported.json()["error_rows"] == 1

        errors = client.get(
            f"/api/v1/imports/batches/{imported.json()['import_batch_id']}/errors"
        )
        assert any(err["field_name"] == "cpe" for err in errors.json())


def test_reimport_preserves_profile_fields() -> None:
    """An incremental daily import without compliance columns must not wipe the
    compliance/conversion fields an earlier import provided."""
    platform_uid = f"keep_{uuid4().hex}"
    full = {
        "accounts": [
            {
                "platform_uid": platform_uid,
                "nickname": "增量导入",
                "ad_compliance_rate": 0.95,
                "shadowban_risk": 0.02,
                "snapshots": [
                    {"data_date": "2026-06-19", "fans_count": 100, "fans_delta": 5}
                ],
            }
        ]
    }
    incremental = {
        "accounts": [
            {
                "platform_uid": platform_uid,
                "nickname": "增量导入",
                "snapshots": [
                    {"data_date": "2026-06-20", "fans_count": 150, "fans_delta": 50}
                ],
            }
        ]
    }

    with TestClient(app) as client:
        assert client.post("/api/v1/imports/accounts", json=full).status_code == 200
        assert client.post("/api/v1/imports/accounts", json=incremental).status_code == 200

        from sqlalchemy import select as sa_select

        from xhs_health.db import SessionLocal
        from xhs_health.models import Account as AccountModel

        session = SessionLocal()
        try:
            account = session.scalar(
                sa_select(AccountModel).where(AccountModel.platform_uid == platform_uid)
            )
            assert float(account.ad_compliance_rate) == 0.95
            assert float(account.shadowban_risk) == 0.02
        finally:
            session.close()


def test_note_conflict_rejects_whole_payload_atomically() -> None:
    """A payload with a conflicting note_id must be rejected in full — the old
    flow wrote the account and snapshots, then 'rejected' the row."""
    from sqlalchemy import select as sa_select

    from xhs_health.db import SessionLocal
    from xhs_health.models import Account as AccountModel

    shared_note = f"note_{uuid4().hex}"
    uid_a, uid_b = f"uid_{uuid4().hex}", f"uid_{uuid4().hex}"
    snapshot = {"data_date": "2026-06-19", "fans_count": 100, "fans_delta": 5}

    with TestClient(app) as client:
        first = client.post(
            "/api/v1/imports/accounts",
            json={
                "accounts": [
                    {
                        "platform_uid": uid_a,
                        "nickname": "A",
                        "snapshots": [snapshot],
                        "notes": [{"note_id": shared_note}],
                    }
                ]
            },
        )
        assert first.status_code == 200

        second = client.post(
            "/api/v1/imports/accounts",
            json={
                "accounts": [
                    {
                        "platform_uid": uid_b,
                        "nickname": "B",
                        "snapshots": [snapshot],
                        "notes": [{"note_id": shared_note}],
                    }
                ]
            },
        )
        assert second.status_code == 200
        body = second.json()
        assert body["accounts_upserted"] == 0
        assert body["error_rows"] == 1

        session = SessionLocal()
        try:
            account_b = session.scalar(
                sa_select(AccountModel).where(AccountModel.platform_uid == uid_b)
            )
            assert account_b is None, "rejected payload must not leave an account behind"
        finally:
            session.close()


def test_import_file_size_cap(monkeypatch) -> None:
    monkeypatch.setattr("xhs_health.api.imports.MAX_IMPORT_FILE_BYTES", 16)
    csv_body = b"platform_uid,nickname,data_date\nx,y,2026-06-19\n" + b"#"
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/imports/account-metrics-file",
            files={"file": ("big.csv", csv_body, "text/csv")},
        )
        assert response.status_code == 413


def test_errors_csv_survives_hostile_text() -> None:
    """Quotes/newlines/commas in nicknames and messages must round-trip through
    the error CSV without corrupting row structure."""
    suffix = uuid4().hex
    payload = {
        "accounts": [
            {
                "platform_uid": f"evil_{suffix}",
                "nickname": 'a\nb",=1+1"x',
                "ad_compliance_rate": 1.5,  # triggers the error row
                "snapshots": [{"data_date": "2026-06-19", "fans_count": 100}],
            }
        ]
    }

    with TestClient(app) as client:
        imported = client.post("/api/v1/imports/accounts", json=payload)
        assert imported.status_code == 200
        batch_id = imported.json()["import_batch_id"]

        import csv as csv_mod
        import io

        download = client.get(f"/api/v1/imports/batches/{batch_id}/errors.csv")
        assert download.status_code == 200
        rows = list(csv_mod.reader(io.StringIO(download.text)))
        assert rows[0] == ["row_number", "field_name", "message", "raw_payload"]
        data_rows = [r for r in rows[1:] if r]
        assert data_rows, "error rows must be present"
        for row in data_rows:
            assert len(row) == 4, f"corrupted row: {row!r}"
