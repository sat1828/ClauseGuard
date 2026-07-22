import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api } from '../api/client';
import RiskBadge from '../components/RiskBadge';
import ClauseCard from '../components/ClauseCard';
import FlagBanner from '../components/FlagBanner';
import Disclaimer from '../components/Disclaimer';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import './DocumentResults.css';

const POLL_INTERVAL_MS = 2500;

const PROGRESS_MESSAGES = [
  'Parsing document…',
  'Segmenting into clauses…',
  'Analyzing clauses…',
  'Finalizing scores…',
];

export default function DocumentResults() {
  const { documentId } = useParams();
  useDocumentTitle('Contract analysis');
  const [status, setStatus] = useState(null);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);
  const [sortBy, setSortBy] = useState('risk'); // 'risk' | 'order'
  const pollRef = useRef(null);
  const clauseRefs = useRef({});

  const fetchStatus = useCallback(async () => {
    try {
      const s = await api.getStatus(documentId);
      setStatus(s);
      if (s.status === 'complete' || s.status === 'failed') {
        clearInterval(pollRef.current);
        if (s.status === 'complete') {
          const r = await api.getResults(documentId);
          setResults(r);
        }
      }
    } catch (err) {
      setError(err.message);
      clearInterval(pollRef.current);
    }
  }, [documentId]);

  useEffect(() => {
    fetchStatus();
    pollRef.current = setInterval(fetchStatus, POLL_INTERVAL_MS);
    return () => clearInterval(pollRef.current);
  }, [fetchStatus]);

  const jumpToClause = (clauseId) => {
    const el = clauseRefs.current[clauseId];
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  };

  if (error) {
    return (
      <div className="container doc-results">
        <div className="form-error" role="alert">{error}</div>
        <Link to="/dashboard" className="btn btn--secondary">Back to dashboard</Link>
      </div>
    );
  }

  if (!status || status.status === 'pending' || status.status === 'processing') {
    const progressIndex = status?.status === 'processing'
      ? Math.min(2, Math.floor((status.clauses_processed / Math.max(status.clauses_total, 1)) * 4))
      : 0;
    return (
      <div className="container doc-results doc-results--processing">
        <div className="processing-card card glass">
          <div className="processing-card__spinner" aria-hidden="true" />
          <h2>{PROGRESS_MESSAGES[progressIndex]}</h2>
          {status?.clauses_total > 0 && (
            <p className="processing-card__count">
              {status.clauses_processed} of {status.clauses_total} clauses analyzed
            </p>
          )}
          <div className="processing-card__bar">
            <div
              className="processing-card__bar-fill"
              style={{
                width: status?.clauses_total
                  ? `${Math.max(5, (status.clauses_processed / status.clauses_total) * 100)}%`
                  : '5%',
              }}
            />
          </div>
        </div>
      </div>
    );
  }

  if (status.status === 'failed') {
    return (
      <div className="container doc-results">
        <div className="card processing-card">
          <h2>Analysis failed</h2>
          <p className="processing-card__count">{status.error_message || 'Something went wrong processing this document.'}</p>
          <Link to="/dashboard" className="btn btn--secondary" style={{ marginTop: 'var(--space-4)' }}>
            Back to dashboard
          </Link>
        </div>
      </div>
    );
  }

  if (!results) return <div className="page-loading">Loading results…</div>;

  const sortedClauses = [...results.clauses].sort((a, b) => {
    if (sortBy === 'order') return a.clause_index - b.clause_index;
    return (b.risk_score || 0) - (a.risk_score || 0);
  });

  return (
    <div className="container doc-results">
      <Disclaimer />

      <div className="doc-header card glass">
        <div>
          <p className="doc-header__label">Overall risk</p>
          <div className="doc-header__score-row">
            <span className="doc-header__score mono">
              {results.overall_risk_score != null ? results.overall_risk_score.toFixed(1) : '—'}
            </span>
            <RiskBadge level={results.overall_risk_label} size="lg" />
          </div>
        </div>
        <div className="doc-header__meta">
          <span>{results.filename}</span>
          <span>{results.page_count} pages · {results.word_count} words</span>
          {results.used_ocr && <span>Processed via OCR</span>}
        </div>
      </div>

      {results.partial_analysis && (
        <div className="form-error" role="alert">
          {results.clauses_failed} clause(s) could not be analyzed. Results below may be incomplete.
        </div>
      )}
      {results.truncated && (
        <div className="form-error" role="alert">
          This document had more clauses than we could process in one pass. Showing the first {results.clauses_total}.
        </div>
      )}

      {results.flags.length > 0 && (
        <section className="doc-flags">
          {results.flags.map((flag) => (
            <FlagBanner key={flag.id} flag={flag} onJump={jumpToClause} />
          ))}
        </section>
      )}

      <div className="doc-clauses__header">
        <h2>Clauses ({results.clauses.length})</h2>
        <div className="doc-clauses__sort" role="group" aria-label="Sort clauses">
          <button
            className={sortBy === 'risk' ? 'active' : ''}
            onClick={() => setSortBy('risk')}
          >
            Highest risk first
          </button>
          <button
            className={sortBy === 'order' ? 'active' : ''}
            onClick={() => setSortBy('order')}
          >
            Document order
          </button>
        </div>
      </div>

      <div className="doc-clauses__list">
        {sortedClauses.map((clause) => (
          <div key={clause.id} ref={(el) => { clauseRefs.current[clause.id] = el; }}>
            <ClauseCard clause={clause} index={clause.clause_index} />
          </div>
        ))}
      </div>

      <Disclaimer />
    </div>
  );
}
