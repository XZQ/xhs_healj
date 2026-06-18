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
