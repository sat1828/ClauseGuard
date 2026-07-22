import { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import './Auth.css';

export default function VerifyEmail() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';
  const { refreshUser, user } = useAuth();
  useDocumentTitle('Verify your email');

  const [status, setStatus] = useState(token ? 'verifying' : 'missing_token');
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!token) return;
    api.verifyEmail(token)
      .then(() => {
        setStatus('success');
        if (user) refreshUser();
      })
      .catch((err) => {
        setStatus('error');
        setError(err.message || 'This link may be invalid or expired.');
      });
  }, [token]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="auth-page">
      <div className="auth-card card glass">
        <h1>Email verification</h1>

        {status === 'verifying' && <p className="auth-card__sub">Verifying your email…</p>}

        {status === 'success' && (
          <div className="billing-notice">Your email is verified. You're all set.</div>
        )}

        {status === 'error' && (
          <div className="form-error" role="alert">{error}</div>
        )}

        {status === 'missing_token' && (
          <div className="form-error" role="alert">
            No verification token found in this link.
          </div>
        )}

        <p className="auth-card__footer">
          <Link to={user ? '/dashboard' : '/login'}>
            {user ? 'Go to dashboard' : 'Back to log in'}
          </Link>
        </p>
      </div>
    </div>
  );
}
