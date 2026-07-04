from uuid import uuid4

from fastapi.testclient import TestClient

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

