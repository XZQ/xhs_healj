from xhs_health.services.scoring import HealthScoreEngine, ScoreThresholds


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


# ---------- Boundary / regression tests ----------

def _full_account_data() -> dict:
    return {
        "violation_count_180d": 0,
        "ad_compliance_rate": 1.0,
        "audit_pass_rate": 0.98,
        "shadowban_risk": 0.02,
        "fan_quality_score": 0.8,
        "cpe": 2.0,
        "avg_cpe_benchmark": 3.0,
        "business_stability": 0.9,
    }


def test_empty_snapshots_returns_unknown_data_dimension() -> None:
    result = HealthScoreEngine().calculate(
        account_data=_full_account_data(),
        snapshots=[],
        notes=[],
    )
    assert result.dimensions["data"].status == "unknown"
    assert result.dimensions["content"].status == "unknown"
    assert result.confidence_level == "Low"
    assert "snapshot.fans_count" in result.missing_fields


def test_fans_zero_does_not_crash() -> None:
    result = HealthScoreEngine().calculate(
        account_data=_full_account_data(),
        snapshots=[
            {
                "data_date": "2026-06-19",
                "fans_count": 0,
                "fans_delta": 0,
                "total_reads": 0,
                "total_likes": 0,
                "total_collects": 0,
                "total_comments": 0,
                "total_shares": 0,
                "publish_count": 0,
            }
        ],
        notes=[],
    )
    # Should not crash, score should be bounded.
    assert 0 <= result.total_score <= 100
    assert result.dimensions["data"].indicators["fans_growth_rate"] is None


def test_negative_growth_triggers_penalty_and_warning() -> None:
    result = HealthScoreEngine().calculate(
        account_data=_full_account_data(),
        snapshots=[
            {
                "data_date": "2026-06-19",
                "fans_count": 9_900,
                "fans_delta": -500,
                "total_reads": 100_000,
                "total_likes": 4_000,
                "total_collects": 900,
                "total_comments": 100,
                "total_shares": 100,
                "publish_count": 1,
            }
        ],
        notes=[
            {"note_id": "n1", "read_count": 20_000, "cqi": 0.08,
             "is_original": True, "tags": ["x"]},
        ],
    )
    assert result.dimensions["data"].penalty > 0
    assert "data_penalty" in result.warning_flags


def test_high_shadowban_risk_caps_compliance_score() -> None:
    data = _full_account_data()
    data["shadowban_risk"] = 0.5
    result = HealthScoreEngine().calculate(
        account_data=data,
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
            {"note_id": "n1", "read_count": 20_000, "cqi": 0.08,
             "is_original": True, "tags": ["x"]},
        ],
    )
    assert result.dimensions["compliance"].final_score is not None
    assert result.dimensions["compliance"].final_score < 60
    assert "compliance_penalty" in result.warning_flags


def test_total_score_never_exceeds_100_or_drops_below_0() -> None:
    # Pathological inputs: very high values everywhere.
    result = HealthScoreEngine().calculate(
        account_data={
            "violation_count_180d": 0,
            "ad_compliance_rate": 1.0,
            "audit_pass_rate": 1.0,
            "shadowban_risk": 0.0,
            "fan_quality_score": 1.0,
            "cpe": 0.1,
            "avg_cpe_benchmark": 100.0,
            "business_stability": 1.0,
        },
        snapshots=[
            {
                "data_date": "2026-06-19",
                "fans_count": 10_000_000,
                "fans_delta": 1_000_000,
                "total_reads": 10_000_000,
                "total_likes": 5_000_000,
                "total_collects": 5_000_000,
                "total_comments": 5_000_000,
                "total_shares": 5_000_000,
                "publish_count": 5,
            }
        ],
        notes=[
            {"note_id": "n1", "read_count": 1_000_000, "cqi": 0.5,
             "is_original": True, "tags": ["x", "x"]},
        ],
    )
    assert 0.0 <= result.total_score <= 100.0


def test_health_level_buckets_use_thresholds() -> None:
    # Engine with all level cut-offs shifted very high → even a perfect score ends up "E".
    extreme = ScoreThresholds(level_a=200.0, level_b=200.0, level_c=200.0, level_d=200.0)
    result = HealthScoreEngine(thresholds=extreme).calculate(
        account_data=_full_account_data(),
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
            {"note_id": "n1", "read_count": 20_000, "cqi": 0.08,
             "is_original": True, "tags": ["x"]},
        ],
    )
    assert result.health_level == "E"


def test_confidence_low_when_many_dimensions_unknown() -> None:
    # Only data dimension has inputs.
    result = HealthScoreEngine().calculate(
        account_data={},
        snapshots=[
            {
                "data_date": "2026-06-19",
                "fans_count": 1000,
                "fans_delta": 10,
                "total_reads": 5000,
                "total_likes": 200,
                "total_collects": 50,
                "total_comments": 20,
                "total_shares": 10,
                "publish_count": 1,
            }
        ],
        notes=[],
    )
    assert result.confidence_level == "Low"


