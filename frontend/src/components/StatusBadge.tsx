import { humanize } from '../utils/format';

type StatusTone = 'neutral' | 'positive' | 'warning' | 'critical' | 'info';

const critical = new Set(['failed', 'avoid', 'critical', 'clearance watch']);
const warning = new Set(['mapping required', 'warning', 'monitor', 'processing']);
const positive = new Set(['completed', 'growth', 'cash cow', 'ready']);
const info = new Set(['uploaded', 'test buy', 'discovery', 'premium margin', 'duplicate']);

function toneFor(value: string): StatusTone {
  const normalized = value.toLowerCase().replace(/[_-]+/g, ' ');
  if (critical.has(normalized)) return 'critical';
  if (warning.has(normalized)) return 'warning';
  if (positive.has(normalized)) return 'positive';
  if (info.has(normalized)) return 'info';
  return 'neutral';
}

export function StatusBadge({ value, prefix }: { value: string; prefix?: string }) {
  const tone = toneFor(value);
  return (
    <span className={`status-badge status-badge--${tone}`}>
      <span aria-hidden="true" className="status-badge__mark">
        {tone === 'critical' ? '!' : tone === 'warning' ? '△' : tone === 'positive' ? '✓' : '•'}
      </span>
      {prefix ? `${prefix}: ` : ''}
      {humanize(value)}
    </span>
  );
}
