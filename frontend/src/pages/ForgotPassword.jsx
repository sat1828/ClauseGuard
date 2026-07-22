import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import './Auth.css';

export default function ForgotPassword() {
  useDocumentTitle('Reset your password');
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api.requestPasswordReset(email);
      setSent(true);
    } catch (err) {
      // The backend never reveals whether the email exists, but a genuine
      // network/server error should still surface.
      setError(err.message || 'Something went wrong. Try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card card glass">
        <h1>Reset your password</h1>
        <p className="auth-card__sub">
          We'll email you a link to reset it — if that address has an account.
        </p>

        {error && <div className="form-error" role="alert">{error}</div>}

        {sent ? (
          <div className="billing-notice">
            If an account exists for that email, a reset link is on its way.
            Check your inbox (and spam folder).
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <div className="field">
              <label htmlFor="email">Email</label>
              <input
                id="email" type="email" required autoComplete="email"
                value={email} onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <button type="submit" className="btn btn--primary btn--full" disabled={submitting}>
              {submitting ? 'Sending…' : 'Send reset link'}
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
