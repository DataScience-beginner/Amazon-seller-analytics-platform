import type { Score } from '../api/contracts';
import { humanize } from '../utils/format';

export function ScoreDisplay({ score }: { score: Score }) {
  const value = Math.max(0, Math.min(100, score.value));
  const label = score.label ?? `${humanize(score.name)} Score`;
  return (
    <div className="score-display">
      <div className="score-display__heading">
        <span>{label}</span>
        <strong>{value.toFixed(0)} / 100</strong>
      </div>
      <progress max="100" value={value} aria-label={label}>
        {value}
      </progress>
      {score.formula_version && <small>Formula {score.formula_version}</small>}
    </div>
  );
}
