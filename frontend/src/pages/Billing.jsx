import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api, ApiError } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import './Billing.css';

const PLANS = [
  {
    id: 'free', name: 'Free', price: '$0', period: '',
    features: ['3 contract analyses', 'Risk scores + plain-English explanations'],
  },
  {
    id: 'starter', name: 'Starter', price: '$19', period: '/month',
    features: ['20 analyses / month', 'Safer language suggestions', 'Flag highlights'],
  },
  {
    id: 'pro', name: 'Pro', price: '$49', period: '/month',
    features: ['500 analyses / month (fair-use ceiling)', 'Everything in Starter', 'Priority processing'],
  },
];

export default function Billing() {
  const { user, refreshUser } = useAuth();
  useDocumentTitle('Plans & billing');
  const [searchParams] = useSearchParams();
  const [loadingPlan, setLoadingPlan] = useState(null);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);

  useEffect(() => {
    if (searchParams.get('checkout') === 'success') {
      setNotice('Payment received — your plan will update within a few seconds once Stripe confirms it.');
      refreshUser();
    } else if (searchParams.get('checkout') === 'canceled') {
      setNotice('Checkout canceled — you have not been charged.');
    }
  }, [searchParams, refreshUser]);

  const handleUpgrade = async (planId) => {
    setError(null);
    setLoadingPlan(planId);
    try {
      const res = await api.createCheckoutSession(planId);
      window.location.href = res.checkout_url;
    } catch (err) {
      if (err instanceof ApiError && err.status === 503) {
        setError(
          "Payments aren't configured on this server yet (missing Stripe keys). " +
          "If you're the operator: add STRIPE_SECRET_KEY and STRIPE_PRICE_* to the backend .env."
        );
      } else {
        setError(err.message || 'Could not start checkout.');
      }
    } finally {
      setLoadingPlan(null);
    }
  };

  return (
    <div className="container billing-page">
      <h1>Plans</h1>
      <p className="billing-page__sub">
        You're currently on the <strong>{user?.plan}</strong> plan
        ({user?.analyses_used}/{user?.analyses_limit} analyses used).
      </p>

      {notice && <div className="billing-notice">{notice}</div>}
      {error && <div className="form-error" role="alert">{error}</div>}

      <div className="billing-plans">
        {PLANS.map((plan) => {
          const isCurrent = user?.plan === plan.id;
          return (
            <div key={plan.id} className={`plan-card card glass ${isCurrent ? 'plan-card--current' : ''}`}>
              {isCurrent && <span className="plan-card__badge">Current plan</span>}
              <h2>{plan.name}</h2>
              <p className="plan-card__price">
                {plan.price}<span>{plan.period}</span>
              </p>
              <ul className="plan-card__features">
                {plan.features.map((f) => <li key={f}>{f}</li>)}
              </ul>
              {plan.id !== 'free' && !isCurrent && (
                <button
                  className="btn btn--primary btn--full"
                  onClick={() => handleUpgrade(plan.id)}
                  disabled={loadingPlan !== null}
                >
                  {loadingPlan === plan.id ? 'Redirecting to checkout…' : `Upgrade to ${plan.name}`}
                </button>
              )}
              {isCurrent && <button className="btn btn--secondary btn--full" disabled>Current plan</button>}
            </div>
          );
        })}
      </div>

      <p className="billing-page__note">
        Payments are processed by Stripe. ClauseGuard never sees or stores your card details.
      </p>
    </div>
  );
}
