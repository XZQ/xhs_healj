import type { Score } from "../../types";
import { scoreTone, scoreLabel } from "../../lib/format";

/**
 * ScoreOrb — 详情页健康评分球。
 * tone 由 scoreTone() 推导，映射到 styles.css 的 .score-orb.good/.stable/.watch/.risk/.muted。
 */
export function ScoreOrb({ score }: { score?: Score | null }) {
  if (!score) {
    return (
      <div className="score-orb muted" role="status">
        <strong>--</strong>
        <span>未评分</span>
      </div>
    );
  }
  return (
    <div className={`score-orb ${scoreTone(score)}`} role="status" aria-label={`健康评分 ${score.total_score.toFixed(1)}`}>
      <strong>{score.total_score.toFixed(1)}</strong>
      <span>{scoreLabel(score)}</span>
    </div>
  );
}
