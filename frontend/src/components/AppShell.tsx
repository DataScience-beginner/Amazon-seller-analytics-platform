import { useEffect, useState } from 'react';

import { fetchHealth } from '../api/client';
import type { HealthResponse } from '../types/health';

const navItems = ['Dashboard', 'Products', 'Planning', 'Imports'];

export function AppShell() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchHealth()
      .then((data) => {
        setHealth(data);
        setError(null);
      })
      .catch((caught: unknown) => {
        setError(caught instanceof Error ? caught.message : 'Unable to reach API');
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="Primary navigation">
        <div className="brand">
          SellerOS
          <span>Amazon Seller Operating System</span>
        </div>
        <nav>
          {navItems.map((item) => (
            <a href={`#${item.toLowerCase()}`} key={item}>
              {item}
            </a>
          ))}
        </nav>
      </aside>
      <main className="main-content">
        <header className="hero">
          <p className="eyebrow">Phase 0 foundation</p>
          <h1>SellerOS command centre</h1>
          <p>
            A SaaS-ready modular monolith for turning dynamic Keepa exports and seller-entered
            business data into explainable portfolio decisions.
          </p>
          <div className="health-card" role="status">
            {loading && <span>Checking API health…</span>}
            {error && <span className="error">API health unavailable: {error}</span>}
            {health && (
              <span className="ok">
                API {health.status}; database {health.database}
              </span>
            )}
          </div>
        </header>
        <section className="tiles" aria-label="Navigation placeholders">
          {navItems.map((item) => (
            <article key={item}>
              <h2>{item}</h2>
              <p>Placeholder ready for Phase 1 workflow implementation.</p>
            </article>
          ))}
        </section>
      </main>
    </div>
  );
}
