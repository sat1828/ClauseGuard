import { Link } from 'react-router-dom';
import { useDocumentTitle } from '../hooks/useDocumentTitle';

export default function NotFound() {
  useDocumentTitle('Page not found');
  return (
    <div className="container empty-state" style={{ paddingTop: '80px' }}>
      <h3>Page not found</h3>
      <p style={{ marginBottom: 'var(--space-4)' }}>That page doesn't exist.</p>
      <Link to="/" className="btn btn--primary">Back home</Link>
    </div>
  );
}
