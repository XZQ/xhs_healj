from xhs_health.services.scoring import HealthScoreEngine


def test_missing_compliance_is_unknown_not_full_score() -> None:
    result = HealthScoreEngine().calculate(
        account_data={
            "fan_quality_score": 0.7,
            "cpe": 2.0,
            "avg_cpe_benchmark": 3.0,
            "business_stability": 0.8,
        },
        snapshots=[
            {
                "data_date": "2026-06-19",
                "fans_count": 50_000,
                "fans_delta": 500,
                "total_reads": 100_000,
                "total_likes": 3_000,
                "total_collects": 1_500,
                "total_comments": 300,
                "total_shares": 100,
                "publish_count": 1,
            }
        ],
        notes=[
            {
                "note_id": "n1",
                "read_count": 10_000,
                "cqi": 0.06,
                "is_original": True,
                "tags": ["护肤", "护肤"],
            }
        ],
    )

    assert result.dimensions["compliance"].status == "unknown"
    assert "compliance_unknown" in result.warning_flags
    assert result.confidence_level in {"Medium", "Low"}
    assert "account.ad_compliance_rate" in result.missing_fields


def test_score_uses_decimal_ratio_units() -> None:
    result = HealthScoreEngine().calculate(
        account_data={
            "violation_count_180d": 0,
            "ad_compliance_rate": 1.0,
            "audit_pass_rate": 0.98,
            "shadowban_risk": 0.02,
            "fan_quality_score": 0.8,
            "cpe": 2.0,
            "avg_cpe_benchmark": 3.0,
            "business_stability": 0.9,
        },
        snapshots=[
            {
                "data_date": "2026-06-19",
                "fans_count": 10_500,
                "fans_delta": 500,
                "total_reads": 100_000,
                "total_likes": 4_000,
                "total_collects": 900,
                "total_comments": 100,
                "total_shares": 100,
                "publish_count": 1,
            }
        ],
        notes=[
            {
                "note_id": "n1",
                "read_count": 20_000,
                "cqi": 0.08,
                "is_original": True,
                "tags": ["美妆", "护肤"],
            }
        ],
    )

    assert result.dimensions["data"].indicators["fans_growth_rate"] == 0.05
    assert result.dimensions["data"].indicators["interaction_rate"] == 0.051
    assert result.confidence_level == "High"

