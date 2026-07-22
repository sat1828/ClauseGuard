import Navbar from './Navbar';

export default function Layout({ children }) {
  return (
    <>
      <div className="ambient-field" aria-hidden="true" />
      <Navbar />
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        {children}
      </main>
    </>
  );
}
