from dataclasses import asdict, dataclass, field
from math import log10
from statistics import mean
from typing import Any


MODEL_VERSION = "rules_v1"


@dataclass(frozen=True)
class ScoreWeights:
    data: float = 0.35
    content: float = 0.30
    compliance: float = 0.25
    conversion: float = 0.10


@dataclass
class DimensionScore:
    name: str
    score: float | None
    final_score: float | None
    indicators: dict[str, Any] = field(default_factory=dict)
    penalty: float = 0.0
    penalty_reasons: list[str] = field(default_factory=list)
    status: str = "known"


@dataclass
class HealthScoreResult:
    total_score: float
    health_level: str
    dimensions: dict[str, DimensionScore]
    data_completeness: float
    confidence_level: str
    missing_fields: list[str]
    warning_flags: list[str]
    suggestions: list[str]
    model_version: str = MODEL_VERSION

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["dimensions"] = {key: asdict(value) for key, value in self.dimensions.items()}
        return data


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return numerator / denominator


def _bounded(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _score_level(score: float) -> str:
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    if score >= 40:
        return "D"
    return "E"


class HealthScoreEngine:
    def __init__(self, weights: ScoreWeights | None = None) -> None:
        self.weights = weights or ScoreWeights()

    def calculate(
        self,
        account_data: dict[str, Any],
        snapshots: list[dict[str, Any]],
        notes: list[dict[str, Any]],
    ) -> HealthScoreResult:
        missing_fields = self._missing_fields(account_data, snapshots, notes)
        completeness = self._data_completeness(missing_fields)

        data_dim = self._data_dimension(snapshots)
        content_dim = self._content_dimension(notes)
        compliance_dim = self._compliance_dimension(account_data)
        conversion_dim = self._conversion_dimension(account_data)

        dimensions = {
            "data": data_dim,
            "content": content_dim,
            "compliance": compliance_dim,
            "conversion": conversion_dim,
        }
        total_score = self._weighted_total(dimensions)
        confidence_level = self._confidence_level(completeness, dimensions)
        warning_flags = self._warning_flags(dimensions, confidence_level)
        suggestions = self._suggestions(dimensions, confidence_level)

        return HealthScoreResult(
            total_score=round(total_score, 2),
            health_level=_score_level(total_score),
            dimensions=dimensions,
            data_completeness=round(completeness, 4),
            confidence_level=confidence_level,
            missing_fields=missing_fields,
            warning_flags=warning_flags,
            suggestions=suggestions,
        )

    def _weighted_total(self, dimensions: dict[str, DimensionScore]) -> float:
        raw_weights = {
            "data": self.weights.data,
            "content": self.weights.content,
            "compliance": self.weights.compliance,
            "conversion": self.weights.conversion,
        }
        available = {
            name: dim.final_score
            for name, dim in dimensions.items()
            if dim.final_score is not None and dim.status == "known"
        }
        if not available:
            return 0.0
        total_weight = sum(raw_weights[name] for name in available)
        return sum((raw_weights[name] / total_weight) * score for name, score in available.items())

    def _data_dimension(self, snapshots: list[dict[str, Any]]) -> DimensionScore:
        if not snapshots:
            return DimensionScore("数据指标", None, None, status="unknown")

        latest = sorted(snapshots, key=lambda row: row.get("data_date"))[-1]
        fans = _to_float(latest.get("fans_count"))
        fans_delta = _to_float(latest.get("fans_delta"))
        reads = _to_float(latest.get("total_reads"))
        interactions = sum(
            _to_float(latest.get(key)) or 0
            for key in ("total_likes", "total_collects", "total_comments", "total_shares")
        )
        publish_counts = [_to_float(row.get("publish_count")) for row in snapshots]
        publish_counts = [value for value in publish_counts if value is not None]

        fans_score = _bounded(log10(max(fans or 1, 1)) / log10(1_000_000) * 100)

        previous_fans = (fans - fans_delta) if fans is not None and fans_delta is not None else None
        growth_rate = _ratio(fans_delta, previous_fans)
        if growth_rate is None:
            growth_score = None
        elif growth_rate >= 0.05:
            growth_score = 100
        elif growth_rate >= 0.02:
            growth_score = 80
        elif growth_rate > 0:
            growth_score = 60
        elif growth_rate >= -0.02:
            growth_score = 40
        else:
            growth_score = 20

        interaction_rate = _ratio(interactions, reads)
        if interaction_rate is None:
            interaction_score = None
        elif interaction_rate >= 0.08:
            interaction_score = 100
        elif interaction_rate >= 0.05:
            interaction_score = 85
        elif interaction_rate >= 0.03:
            interaction_score = 70
        elif interaction_rate >= 0.01:
            interaction_score = 50
        else:
            interaction_score = 30

        publish_frequency = mean(publish_counts) if publish_counts else None
        if publish_frequency is None:
            publish_score = None
        elif publish_frequency >= 1.0:
            publish_score = 100
        elif publish_frequency >= 0.5:
            publish_score = 80
        elif publish_frequency >= 0.3:
            publish_score = 60
        else:
            publish_score = 30

        scores = [
            (fans_score, 0.20),
            (growth_score, 0.25),
            (interaction_score, 0.35),
            (publish_score, 0.20),
        ]
        score = self._average_known(scores)
        penalty, reasons = 0.0, []
        if growth_rate is not None and growth_rate < -0.01:
            penalty += 10
            reasons.append(f"粉丝持续流失（日增长率 {growth_rate:.2%}）")
        if publish_frequency is not None and publish_frequency < 0.1:
            penalty += 10
            reasons.append("发布频率过低，存在停更风险")

        final_score = None if score is None else _bounded(score - penalty)
        return DimensionScore(
            "数据指标",
            None if score is None else round(score, 2),
            None if final_score is None else round(final_score, 2),
            indicators={
                "fans_score": round(fans_score, 2),
                "fans_growth_rate": growth_rate,
                "fans_growth_score": growth_score,
                "interaction_rate": interaction_rate,
                "interaction_rate_score": interaction_score,
                "publish_frequency": publish_frequency,
                "publish_score": publish_score,
            },
            penalty=penalty,
            penalty_reasons=reasons,
        )

    def _content_dimension(self, notes: list[dict[str, Any]]) -> DimensionScore:
        if not notes:
            return DimensionScore("内容质量", None, None, status="unknown")

        original_values = [note.get("is_original") for note in notes if note.get("is_original") is not None]
        original_rate = sum(1 for value in original_values if value) / len(original_values) if original_values else None
        original_score = None if original_rate is None else original_rate * 100

        reads = [_to_float(note.get("read_count")) or 0 for note in notes]
        avg_reads = mean(reads) if reads else 0
        viral_rate = (
            sum(1 for value in reads if avg_reads > 0 and value > avg_reads * 3) / len(reads)
            if reads
            else None
        )
        viral_score = None if viral_rate is None else _bounded(viral_rate * 500)

        cqi_values = [_to_float(note.get("cqi")) for note in notes if note.get("cqi") is not None]
        avg_cqi = mean(cqi_values) if cqi_values else None
        if avg_cqi is None:
            cqi_score = None
        elif avg_cqi >= 0.08:
            cqi_score = 100
        elif avg_cqi >= 0.05:
            cqi_score = 80
        elif avg_cqi >= 0.03:
            cqi_score = 60
        else:
            cqi_score = 40

        verticality_score = self._verticality_score(notes)
        score = self._average_known(
            [
                (original_score, 0.20),
                (viral_score, 0.25),
                (cqi_score, 0.30),
                (verticality_score, 0.25),
            ]
        )
        return DimensionScore(
            "内容质量",
            None if score is None else round(score, 2),
            None if score is None else round(_bounded(score), 2),
            indicators={
                "original_rate": original_rate,
                "original_rate_score": None if original_score is None else round(original_score, 2),
                "viral_rate": viral_rate,
                "viral_rate_score": None if viral_score is None else round(viral_score, 2),
                "avg_cqi": avg_cqi,
                "cqi_score": cqi_score,
                "verticality_score": verticality_score,
            },
        )

    def _compliance_dimension(self, account_data: dict[str, Any]) -> DimensionScore:
        keys = ("violation_count_180d", "ad_compliance_rate", "audit_pass_rate", "shadowban_risk")
        if all(account_data.get(key) is None for key in keys):
            return DimensionScore("合规风险", None, None, status="unknown")

        penalty, reasons = 0.0, []
        violation_count = account_data.get("violation_count_180d")
        if violation_count is None:
            violation_score = None
        elif violation_count == 0:
            violation_score = 100
        elif violation_count == 1:
            violation_score = 60
            penalty += 20
            reasons.append("近 180 天有 1 次违规记录")
        else:
            violation_score = 20
            penalty += 40
            reasons.append(f"近 180 天有 {violation_count} 次违规记录")

        ad_rate = _to_float(account_data.get("ad_compliance_rate"))
        ad_score = None if ad_rate is None else _bounded(ad_rate * 100)
        if ad_rate is not None and ad_rate < 1:
            penalty += 10
            reasons.append(f"广告标注合规率 {ad_rate:.0%}，存在未标注广告")

        audit_rate = _to_float(account_data.get("audit_pass_rate"))
        audit_score = None if audit_rate is None else _bounded(audit_rate * 100)

        shadowban_risk = _to_float(account_data.get("shadowban_risk"))
        if shadowban_risk is None:
            shadowban_score = None
        elif shadowban_risk < 0.1:
            shadowban_score = 100
        elif shadowban_risk < 0.3:
            shadowban_score = 60
            penalty += 15
            reasons.append("检测到限流风险信号")
        else:
            shadowban_score = 20
            penalty += 30
            reasons.append("限流风险较高，建议排查原因")

        score = self._average_known(
            [
                (violation_score, 0.30),
                (ad_score, 0.25),
                (audit_score, 0.20),
                (shadowban_score, 0.25),
            ]
        )
        final_score = None if score is None else _bounded(score - penalty)
        return DimensionScore(
            "合规风险",
            None if score is None else round(score, 2),
            None if final_score is None else round(final_score, 2),
            indicators={
                "violation_score": violation_score,
                "ad_compliance_score": None if ad_score is None else round(ad_score, 2),
                "audit_pass_score": None if audit_score is None else round(audit_score, 2),
                "shadowban_score": shadowban_score,
            },
            penalty=penalty,
            penalty_reasons=reasons,
        )

    def _conversion_dimension(self, account_data: dict[str, Any]) -> DimensionScore:
        keys = ("fan_quality_score", "cpe", "avg_cpe_benchmark", "business_stability")
        if all(account_data.get(key) is None for key in keys):
            return DimensionScore("转化能力", None, None, status="unknown")

        fan_quality = _to_float(account_data.get("fan_quality_score"))
        fan_quality_score = None if fan_quality is None else _bounded(fan_quality * 100)

        cpe = _to_float(account_data.get("cpe"))
        benchmark = _to_float(account_data.get("avg_cpe_benchmark"))
        if cpe is None or benchmark is None or cpe <= 0:
            cpe_score = None
        else:
            cpe_score = _bounded((benchmark / cpe) * 70)

        stability = _to_float(account_data.get("business_stability"))
        stability_score = None if stability is None else _bounded(stability * 100)

        score = self._average_known(
            [(fan_quality_score, 0.40), (cpe_score, 0.35), (stability_score, 0.25)]
        )
        return DimensionScore(
            "转化能力",
            None if score is None else round(score, 2),
            None if score is None else round(_bounded(score), 2),
            indicators={
                "fan_quality_score": None
                if fan_quality_score is None
                else round(fan_quality_score, 2),
                "cpe_score": None if cpe_score is None else round(cpe_score, 2),
                "stability_score": None if stability_score is None else round(stability_score, 2),
            },
        )

    def _average_known(self, weighted_scores: list[tuple[float | None, float]]) -> float | None:
        known = [(score, weight) for score, weight in weighted_scores if score is not None]
        if not known:
            return None
        total_weight = sum(weight for _, weight in known)
        return sum((weight / total_weight) * score for score, weight in known)

    def _verticality_score(self, notes: list[dict[str, Any]]) -> float | None:
        tags: list[str] = []
        for note in notes:
            tags.extend(note.get("tags") or [])
        if not tags:
            return None
        counts: dict[str, int] = {}
        for tag in tags:
            counts[tag] = counts.get(tag, 0) + 1
        top_count = max(counts.values())
        return round(_bounded((top_count / len(tags)) * 100), 2)

    def _missing_fields(
        self,
        account_data: dict[str, Any],
        snapshots: list[dict[str, Any]],
        notes: list[dict[str, Any]],
    ) -> list[str]:
        missing: list[str] = []
        latest = sorted(snapshots, key=lambda row: row.get("data_date"))[-1] if snapshots else {}
        for key in (
            "fans_count",
            "fans_delta",
            "total_reads",
            "total_likes",
            "total_collects",
            "total_comments",
            "total_shares",
            "publish_count",
        ):
            if latest.get(key) is None:
                missing.append(f"snapshot.{key}")
        for key in (
            "violation_count_180d",
            "ad_compliance_rate",
            "audit_pass_rate",
            "shadowban_risk",
            "fan_quality_score",
            "cpe",
            "avg_cpe_benchmark",
            "business_stability",
        ):
            if account_data.get(key) is None:
                missing.append(f"account.{key}")
        if not notes:
            missing.append("notes")
        return missing

    def _data_completeness(self, missing_fields: list[str]) -> float:
        expected = 17
        return max(0.0, (expected - len(set(missing_fields))) / expected)

    def _confidence_level(
        self, completeness: float, dimensions: dict[str, DimensionScore]
    ) -> str:
        unknown_dimensions = sum(1 for item in dimensions.values() if item.status == "unknown")
        if completeness >= 0.85 and unknown_dimensions == 0:
            return "High"
        if completeness >= 0.60 and unknown_dimensions <= 2:
            return "Medium"
        return "Low"

    def _warning_flags(
        self, dimensions: dict[str, DimensionScore], confidence_level: str
    ) -> list[str]:
        flags = []
        if confidence_level == "Low":
            flags.append("low_confidence")
        for name, dimension in dimensions.items():
            if dimension.status == "unknown":
                flags.append(f"{name}_unknown")
            if dimension.penalty > 0:
                flags.append(f"{name}_penalty")
        return flags

    def _suggestions(
        self, dimensions: dict[str, DimensionScore], confidence_level: str
    ) -> list[str]:
        suggestions = []
        if confidence_level != "High":
            suggestions.append("数据完整度不足，建议补齐缺失字段后再用于高风险决策")
        data = dimensions["data"]
        if data.final_score is not None and data.final_score < 60:
            suggestions.append("数据指标偏弱，建议优先排查互动率、粉丝增长和发布频率")
        content = dimensions["content"]
        if content.final_score is not None and content.final_score < 60:
            suggestions.append("内容质量偏弱，建议提升内容垂直度、原创率和收藏价值")
        compliance = dimensions["compliance"]
        if compliance.final_score is not None and compliance.final_score < 70:
            suggestions.append("存在合规风险，建议核查违规、广告标注和限流信号")
        conversion = dimensions["conversion"]
        if conversion.final_score is not None and conversion.final_score < 60:
            suggestions.append("转化能力偏弱，建议校准报价并优化粉丝画像匹配")
        return suggestions

