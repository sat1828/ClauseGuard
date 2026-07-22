import { Component } from 'react';
import './ErrorBoundary.css';

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    // In a real deployment this is where you'd forward to an error-tracking
    // service. Logged to console for now — no tracking service is wired up,
    // and pretending otherwise would be exactly the kind of overclaim this
    // project has tried hard to avoid elsewhere.
    console.error('ClauseGuard crashed:', error, info);
  }

  handleReload = () => {
    window.location.href = '/';
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-boundary">
          <div className="error-boundary__card">
            <span className="error-boundary__mark" aria-hidden="true">§</span>
            <h1>Something broke on our end</h1>
            <p>
              Not yours — this page hit an unexpected error. Your documents
              and account are unaffected.
            </p>
            <button className="btn btn--primary" onClick={this.handleReload}>
              Back to safety
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
