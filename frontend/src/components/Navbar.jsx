import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';
import './Navbar.css';

export default function Navbar() {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/');
  };

  return (
    <header className="navbar glass">
      <div className="container navbar__inner">
        <Link to="/" className="navbar__brand">
          <span className="navbar__mark" aria-hidden="true">§</span>
          <span>ClauseGuard</span>
        </Link>

        <nav className="navbar__links" aria-label="Primary">
          {user ? (
            <>
              <Link to="/dashboard">Dashboard</Link>
              <Link to="/billing">Billing</Link>
              <Link to="/settings">Settings</Link>
              <span className="navbar__quota mono">
                {user.analyses_used}/{user.analyses_limit} analyses used
              </span>
            </>
          ) : (
            <>
              <Link to="/login">Log in</Link>
              <Link to="/register" className="navbar__cta">Get started</Link>
            </>
          )}

          <button
            type="button"
            className="navbar__theme-toggle"
            onClick={toggleTheme}
            aria-label={theme === 'light' ? 'Switch to dark mode' : 'Switch to light mode'}
          >
            {theme === 'light' ? '🌙' : '☀️'}
          </button>

          {user && (
            <button type="button" className="navbar__logout" onClick={handleLogout}>
              Log out
            </button>
          )}
        </nav>
      </div>
    </header>
  );
}
