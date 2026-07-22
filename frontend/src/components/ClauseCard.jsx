import { useState } from 'react';
import RiskBadge from './RiskBadge';
import './ClauseCard.css';

export default function ClauseCard({ clause, index }) {
  const [showRaw, setShowRaw] = useState(false);
  const [showSafer, setShowSafer] = useState(false);

  if (clause.analysis_failed) {
    return (
      <div className="clause-card clause-card--failed">
        <div className="clause-card__header">
          <span className="clause-card__index mono">§ {String(index + 1).padStart(2, '0')}</span>
          <span className="clause-card__failed-label">Analysis failed</span>
        </div>
        <p className="clause-card__failed-text">
          This clause couldn't be analyzed automatically. Review it manually below.
        </p>
        <pre className="clause-card__raw">{clause.raw_text}</pre>
      </div>
    );
  }

  return (
    <div className={`clause-card clause-card--${clause.risk_label || 'low'}`}>
      <div className="clause-card__header">
        <span className="clause-card__index mono">§ {String(index + 1).padStart(2, '0')}</span>
        <span className="clause-card__type">{clause.clause_type_label}</span>
        <RiskBadge level={clause.risk_label} />
        <span className="clause-card__score mono" title="Risk score out of 10">
          {clause.risk_score}/10
        </span>
      </div>

      {clause.low_confidence && (
        <p className="clause-card__low-confidence">
          ⚠ Low confidence — the AI wasn't fully sure about this one. Verify manually.
        </p>
      )}

      <p className="clause-card__explanation">{clause.plain_english_explanation}</p>

      <div className="clause-card__actions">
        <button type="button" onClick={() => setShowRaw((v) => !v)}>
          {showRaw ? 'Hide original text' : 'Show original text'}
        </button>
        {clause.suggested_safer_language && (
          <button type="button" onClick={() => setShowSafer((v) => !v)}>
            {showSafer ? 'Hide suggested rewrite' : 'Show suggested rewrite'}
          </button>
        )}
      </div>

      {showRaw && (
        <div className="clause-card__panel">
          <span className="clause-card__panel-label">Original clause</span>
          <pre className="clause-card__raw">{clause.raw_text}</pre>
        </div>
      )}

      {showSafer && clause.suggested_safer_language && (
        <div className="clause-card__panel clause-card__panel--safer">
          <span className="clause-card__panel-label">Suggested safer language</span>
          <p>{clause.suggested_safer_language}</p>
        </div>
      )}
    </div>
  );
}
