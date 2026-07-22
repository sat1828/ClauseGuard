import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../api/client';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import './Auth.css';

export default function ResetPassword() {
  useDocumentTitle('Set a new password');
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get('token') || '';

  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    if (!token) {
      setError('This reset link is missing its token. Request a new one.');
      return;
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }

    setSubmitting(true);
    try {
      await api.resetPassword(token, password);
      setSuccess(true);
      setTimeout(() => navigate('/login'), 2000);
    } catch (err) {
      setError(err.message || 'This link may be invalid or expired.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card card glass">
        <h1>Set a new password</h1>

        {!token && (
          <div className="form-error" role="alert">
            No reset token found in this link. <Link to="/forgot-password">Request a new one</Link>.
          </div>
        )}

        {error && <div className="form-error" role="alert">{error}</div>}

        {success ? (
          <div className="billing-notice">
            Password updated. All your other sessions have been logged out for
            safety. Redirecting you to log in…
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <div className="field">
              <label htmlFor="password">New password</label>
              <input
                id="password" type="password" required minLength={8} autoComplete="new-password"
                value={password} onChange={(e) => setPassword(e.target.value)}
              />
              <span className="field-hint">At least 8 characters.</span>
            </div>
            <button type="submit" className="btn btn--primary btn--full" disabled={submitting || !token}>
              {submitting ? 'Updating…' : 'Update password'}
            </button>
          </form>
        )}

        <p className="auth-card__footer">
          <Link to="/login">Back to log in</Link>
        </p>
      </div>
    </div>
  );
}
