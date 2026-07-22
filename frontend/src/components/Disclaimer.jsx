import './Disclaimer.css';

const TEXT = "ClauseGuard provides information, not legal advice. AI analysis may contain errors. For contracts with significant financial or legal exposure, consult a licensed attorney before signing.";

export default function Disclaimer() {
  return (
    <div className="disclaimer" role="note">
      <span className="disclaimer__mark mono" aria-hidden="true">§</span>
      <p>{TEXT}</p>
    </div>
  );
}
