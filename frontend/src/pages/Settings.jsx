import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import './Settings.css';

export default function Settings() {
  const { user, logoutAllDevices } = useAuth();
  useDocumentTitle('Settings');
  const navigate = useNavigate();
  const [resendStatus, setResendStatus] = useState(null);
  const [loggingOutAll, setLoggingOutAll] = useState(false);

  const handleResend = async () => {
    setResendStatus('sending');
    try {
      await api.resendVerification();
      setResendStatus('sent');
    } catch {
      setResendStatus('error');
    }
  };

  const handleLogoutAll = async () => {
    if (!window.confirm('This logs you out on every device, including this one. Continue?')) return;
    setLoggingOutAll(true);
    await logoutAllDevices();
    navigate('/login');
  };

  return (
    <div className="container settings-page">
      <h1>Settings</h1>

      <div className="card settings-section">
        <h2>Account</h2>
        <dl className="settings-list">
          <dt>Email</dt>
          <dd>{user?.email}</dd>
          <dt>Plan</dt>
          <dd style={{ textTransform: 'capitalize' }}>{user?.plan}</dd>
          <dt>Email status</dt>
          <dd>
            {user?.email_verified ? (
              <span className="settings-verified">Verified</span>
            ) : (
              <span className="settings-unverified">
                Not verified
                {resendStatus !== 'sent' && (
                  <button className="settings-inline-btn" onClick={handleResend} disabled={resendStatus === 'sending'}>
                    {resendStatus === 'sending' ? 'Sending…' : 'Resend verification email'}
                  </button>
                )}
                {resendStatus === 'sent' && <span> — Sent, check your inbox.</span>}
                {resendStatus === 'error' && <span> — Couldn't send it, try again shortly.</span>}
              </span>
            )}
          </dd>
        </dl>
      </div>

      <div className="card settings-section">
        <h2>Sessions</h2>
        <p className="settings-section__desc">
          Log out everywhere you're currently signed in — useful if you think
          a device or session might be compromised.
        </p>
        <button className="btn btn--danger" onClick={handleLogoutAll} disabled={loggingOutAll}>
          {loggingOutAll ? 'Logging out everywhere…' : 'Log out of all devices'}
        </button>
      </div>
    </div>
  );
}
