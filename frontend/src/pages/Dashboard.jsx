import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { api, ApiError } from '../api/client';
import { useAuth } from '../context/AuthContext';
import UploadDropzone from '../components/UploadDropzone';
import StatusPill from '../components/StatusPill';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import './Dashboard.css';

const POLL_INTERVAL_MS = 3000;

export default function Dashboard() {
  const { user, refreshUser } = useAuth();
  useDocumentTitle('Your contracts');
  const navigate = useNavigate();
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const pollRef = useRef(null);

  const loadDocuments = useCallback(async () => {
    try {
      const docs = await api.listDocuments();
      setDocuments(docs);
      return docs;
    } catch (err) {
      setError(err.message);
      return [];
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  // Poll while any document is still pending/processing
  useEffect(() => {
    const hasActive = documents.some((d) => d.status === 'pending' || d.status === 'processing');
    if (hasActive) {
      pollRef.current = setInterval(loadDocuments, POLL_INTERVAL_MS);
    }
    return () => clearInterval(pollRef.current);
  }, [documents, loadDocuments]);

  const handleFileSelected = async (file) => {
    setError(null);
    setUploading(true);
    try {
      const res = await api.uploadDocument(file);
      await loadDocuments();
      await refreshUser();
      navigate(`/documents/${res.document_id}`);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setError('You have used all your analyses on the free plan.');
      } else {
        setError(err.message || 'Upload failed.');
      }
    } finally {
      setUploading(false);
    }
  };

  const quotaReached = user && user.analyses_used >= user.analyses_limit;

  return (
    <div className="dashboard container">
      <div className="dashboard__header">
        <div>
          <h1>Your contracts</h1>
          <p className="dashboard__sub">
            {user ? `${user.analyses_used} of ${user.analyses_limit} analyses used on the ${user.plan} plan` : ''}
          </p>
        </div>
      </div>

      {error && <div className="form-error" role="alert">{error}</div>}

      <UploadDropzone onFileSelected={handleFileSelected} disabled={uploading || quotaReached} />
      {uploading && <p className="dashboard__uploading">Uploading and queuing for analysis…</p>}
      {quotaReached && (
        <p className="dashboard__uploading">
          <Link to="/billing">Upgrade your plan</Link> to analyze more contracts.
        </p>
      )}

      <section className="dashboard__list">
        {loading ? (
          <div className="page-loading">Loading your documents…</div>
        ) : documents.length === 0 ? (
          <div className="empty-state">
            <h3>No contracts yet</h3>
            <p>Upload your first contract above to get a plain-English risk breakdown.</p>
          </div>
        ) : (
          documents.map((doc) => (
            <button
              key={doc.id}
              className="doc-row"
              onClick={() => navigate(`/documents/${doc.id}`)}
            >
              <div className="doc-row__main">
                <span className="doc-row__id mono">#{doc.id.slice(0, 8)}</span>
                <StatusPill status={doc.status} />
              </div>
              <div className="doc-row__meta">
                {doc.status === 'processing' && (
                  <span>{doc.clauses_processed}/{doc.clauses_total || '?'} clauses analyzed</span>
                )}
                {doc.status === 'failed' && doc.error_message && (
                  <span className="doc-row__error">{doc.error_message}</span>
                )}
                {doc.status === 'complete' && <span>{doc.clauses_total} clauses analyzed</span>}
              </div>
            </button>
          ))
        )}
      </section>
    </div>
  );
}
