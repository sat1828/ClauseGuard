import './RiskBadge.css';

const LABELS = {
  low: 'Low risk',
  medium: 'Medium risk',
  high: 'High risk',
  critical: 'Critical risk',
};

export default function RiskBadge({ level, size = 'md' }) {
  if (!level) return null;
  return (
    <span className={`risk-badge risk-badge--${level} risk-badge--${size}`}>
      <span className="risk-badge__dot" aria-hidden="true" />
      {LABELS[level] || level}
    </span>
  );
}
