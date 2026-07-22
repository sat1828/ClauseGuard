import './StatusPill.css';

const CONFIG = {
  pending: { label: 'Queued', className: 'status-pill--pending' },
  processing: { label: 'Analyzing…', className: 'status-pill--processing' },
  complete: { label: 'Complete', className: 'status-pill--complete' },
  failed: { label: 'Failed', className: 'status-pill--failed' },
};

export default function StatusPill({ status }) {
  const cfg = CONFIG[status] || { label: status, className: '' };
  return <span className={`status-pill ${cfg.className}`}>{cfg.label}</span>;
}
