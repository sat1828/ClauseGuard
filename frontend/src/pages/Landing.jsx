import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Reveal } from '../components/Reveal';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import './Landing.css';

export default function Landing() {
  const { user } = useAuth();
  useDocumentTitle('Read the fine print before it reads you');

  return (
    <div className="landing snap-container">
      <section className="landing__section landing__hero">
        <div className="container landing__hero-inner">
          <Reveal>
            <p className="landing__eyebrow mono">FOR BUSINESSES WITHOUT IN-HOUSE COUNSEL</p>
          </Reveal>
          <Reveal delay={80}>
            <h1 className="landing__headline">
              Read the fine print<br />before it reads <em>you</em>.
            </h1>
          </Reveal>
          <Reveal delay={160}>
            <p className="landing__sub">
              Upload a vendor contract, SaaS agreement, or freelance deal. ClauseGuard marks up
              every risky clause the way a lawyer would in the margin — in plain English,
              in minutes.
            </p>
          </Reveal>
          <Reveal delay={240}>
            <div className="landing__actions">
              <Link to={user ? '/dashboard' : '/register'} className="btn btn--primary">
                {user ? 'Go to dashboard' : 'Analyze a contract'}
              </Link>
              {!user && <Link to="/login" className="btn btn--secondary">Log in</Link>}
            </div>
          </Reveal>

          <Reveal delay={320}>
            <div className="landing__redline-demo glass" aria-hidden="true">
              <div className="redline-demo__card redline-demo__card--critical">
                <span className="mono">§ 03</span>
                <span>Uncapped Liability</span>
              </div>
              <div className="redline-demo__card redline-demo__card--high">
                <span className="mono">§ 01</span>
                <span>Auto-Renewal</span>
              </div>
              <div className="redline-demo__card redline-demo__card--low">
                <span className="mono">§ 04</span>
                <span>Payment Terms</span>
              </div>
            </div>
          </Reveal>
        </div>
        <div className="landing__scroll-hint" aria-hidden="true">
          <span />
        </div>
      </section>

      <section className="landing__section landing__how">
        <div className="container">
          <Reveal><h2>How it works</h2></Reveal>
          <div className="landing__steps">
            <Reveal delay={0} className="landing__step glass">
              <span className="landing__step-num mono">01</span>
              <h3>Upload</h3>
              <p>Drop in a PDF or DOCX contract. No account setup, no legal jargon required.</p>
            </Reveal>
            <Reveal delay={100} className="landing__step glass">
              <span className="landing__step-num mono">02</span>
              <h3>Analyze</h3>
              <p>Every clause is classified, scored for risk, and explained in plain English.</p>
            </Reveal>
            <Reveal delay={200} className="landing__step glass">
              <span className="landing__step-num mono">03</span>
              <h3>Decide</h3>
              <p>See what's risky, why it matters, and safer language you could ask for instead.</p>
            </Reveal>
          </div>
        </div>
      </section>

      <section className="landing__section landing__closing">
        <div className="container landing__closing-inner">
          <Reveal>
            <h2>Sign with your eyes open.</h2>
          </Reveal>
          <Reveal delay={100}>
            <Link to={user ? '/dashboard' : '/register'} className="btn btn--primary landing__closing-cta">
              {user ? 'Go to dashboard' : 'Analyze your first contract free'}
            </Link>
          </Reveal>
          <Reveal delay={180}>
            <p className="landing__disclaimer-note">
              ClauseGuard is not a law firm and does not provide legal advice.
              For contracts with significant exposure, talk to a licensed attorney.
            </p>
          </Reveal>
        </div>
      </section>
    </div>
  );
}
