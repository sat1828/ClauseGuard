import './FlagBanner.css';

export default function FlagBanner({ flag, onJump }) {
  const [title, ...rest] = flag.summary.split(': ');
  const body = rest.join(': ');
  return (
    <button
      type="button"
      className={`flag-banner flag-banner--${flag.severity}`}
      onClick={() => onJump?.(flag.affected_clause_id)}
    >
      <span className="flag-banner__icon" aria-hidden="true">
        {flag.severity === 'critical' ? '⚠' : '!'}
      </span>
      <span className="flag-banner__text">
        <strong>{title}</strong>
        {body && <span className="flag-banner__body"> — {body}</span>}
      </span>
    </button>
  );
}
