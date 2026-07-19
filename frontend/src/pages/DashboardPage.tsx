import { useCallback } from 'react';

import { fetchDashboard } from '../api/client';
import { Link } from '../app/router';
import { useWorkspace } from '../app/workspace';
import { EmptyState, ErrorState, LoadingState } from '../components/Feedback';
import { PageHeader } from '../components/PageHeader';
import { ProductSummaryRow } from '../components/ProductSummaryRow';
import { StatusBadge } from '../components/StatusBadge';
import { useAsync } from '../hooks/useAsync';
import { formatDate, formatNumber, humanize } from '../utils/format';

export function DashboardPage() {
  const { selection } = useWorkspace();
  const organisationId = selection.workspace.organisation_id;
  const marketplaceId = selection.marketplace.id;
  const load = useCallback(
    (signal: AbortSignal) => fetchDashboard(organisationId, marketplaceId, signal),
    [organisationId, marketplaceId],
  );
  const state = useAsync(load);

  return (
    <>
      <PageHeader
        eyebrow="Command centre"
        title="Portfolio overview"
        description="Prioritise products using observed market evidence, calculated scores and explainable recommendations."
        action={
          <Link className="button" to="/imports">
            Upload Keepa file
          </Link>
        }
      />
      {state.status === 'loading' && <LoadingState label="Calculating your portfolio view…" />}
      {state.status === 'error' && <ErrorState error={state.error} onRetry={state.retry} />}
      {state.status === 'success' && state.data.kpis.tracked_products === 0 && (
        <EmptyState
          title="Your portfolio is ready for its first import"
          action={
            <Link className="button" to="/imports">
              Upload Keepa data
            </Link>
          }
        >
          <p>
            Upload a Keepa .xlsx export to create immutable snapshots and initial recommendations.
          </p>
        </EmptyState>
      )}
      {state.status === 'success' && state.data.kpis.tracked_products > 0 && (
        <div className="dashboard-stack">
          <section className="kpi-grid" aria-label="Portfolio key performance indicators">
            <article className="kpi-card">
              <span>Tracked products</span>
              <strong>{formatNumber(state.data.kpis.tracked_products, 0)}</strong>
              <small>Products with at least one snapshot.</small>
            </article>
            <article className="kpi-card">
              <span>Average opportunity</span>
              <strong>
                {state.data.kpis.average_opportunity_score === undefined
                  ? 'Not available'
                  : `${formatNumber(state.data.kpis.average_opportunity_score)} / 100`}
              </strong>
              <small>Mean latest overall opportunity score.</small>
            </article>
            <article className="kpi-card">
              <span>Classified products</span>
              <strong>{formatNumber(state.data.kpis.classified_products ?? 0, 0)}</strong>
              <small>Latest snapshots with a stored strategy recommendation.</small>
            </article>
            <article className="kpi-card">
              <span>Data-quality alerts</span>
              <strong>{formatNumber(state.data.kpis.data_quality_alerts, 0)}</strong>
              <small>Missing or unreliable evidence requiring attention.</small>
            </article>
          </section>

          <div className="dashboard-grid">
            <section className="panel" aria-labelledby="strategy-heading">
              <div className="section-heading">
                <div>
                  <p className="data-label">Calculated</p>
                  <h2 id="strategy-heading">Strategy distribution</h2>
                </div>
              </div>
              {state.data.strategy_distribution.length === 0 ? (
                <p className="muted">No recommendations have been calculated.</p>
              ) : (
                <ul className="distribution-list">
                  {state.data.strategy_distribution.map((item) => (
                    <li key={item.strategy}>
                      <StatusBadge value={item.strategy} />
                      <strong>{formatNumber(item.count, 0)}</strong>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="panel" aria-labelledby="latest-import-heading">
              <p className="data-label">Observed</p>
              <h2 id="latest-import-heading">Latest import</h2>
              {state.data.latest_import ? (
                <dl className="detail-list">
                  <div>
                    <dt>File</dt>
                    <dd>{state.data.latest_import.filename}</dd>
                  </div>
                  <div>
                    <dt>Status</dt>
                    <dd>
                      <StatusBadge value={state.data.latest_import.status} />
                    </dd>
                  </div>
                  <div>
                    <dt>Completed</dt>
                    <dd>
                      {formatDate(
                        state.data.latest_import.completed_at ??
                          state.data.latest_import.uploaded_at,
                      )}
                    </dd>
                  </div>
                </dl>
              ) : (
                <p className="muted">No imports have been uploaded.</p>
              )}
            </section>
          </div>

          {state.data.data_quality_alerts && state.data.data_quality_alerts.length > 0 && (
            <section className="panel" aria-labelledby="quality-heading">
              <p className="data-label">Needs attention</p>
              <h2 id="quality-heading">Data-quality alerts</h2>
              <ul className="alert-list">
                {state.data.data_quality_alerts.map((alert) => (
                  <li key={alert.code}>
                    <StatusBadge value={alert.severity ?? 'warning'} />
                    <div>
                      <strong>{humanize(alert.code)}</strong>
                      <p>{alert.message}</p>
                    </div>
                    {alert.count !== undefined && (
                      <span>{formatNumber(alert.count, 0)} products</span>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )}

          <section className="panel" aria-labelledby="opportunities-heading">
            <div className="section-heading">
              <div>
                <p className="data-label">Recommended</p>
                <h2 id="opportunities-heading">Top opportunities</h2>
              </div>
              <Link to="/products?sort_by=overall_opportunity&sort_direction=desc">
                View products
              </Link>
            </div>
            {state.data.top_opportunities.length === 0 ? (
              <p className="muted">No opportunity recommendations are available yet.</p>
            ) : (
              <div className="product-summary-list">
                {state.data.top_opportunities.map((product) => (
                  <ProductSummaryRow product={product} key={product.id} />
                ))}
              </div>
            )}
          </section>

          <section className="panel" aria-labelledby="risks-heading">
            <div className="section-heading">
              <div>
                <p className="data-label">Needs attention</p>
                <h2 id="risks-heading">Top risks</h2>
              </div>
            </div>
            {state.data.top_risks.length === 0 ? (
              <p className="muted">No high-priority risks were identified.</p>
            ) : (
              <div className="product-summary-list">
                {state.data.top_risks.map((product) => (
                  <ProductSummaryRow product={product} risk key={product.id} />
                ))}
              </div>
            )}
          </section>

          {state.data.definitions && Object.keys(state.data.definitions).length > 0 && (
            <details className="panel definitions">
              <summary>How dashboard metrics are defined</summary>
              <dl className="detail-list">
                {Object.entries(state.data.definitions).map(([name, definition]) => (
                  <div key={name}>
                    <dt>{humanize(name)}</dt>
                    <dd>{definition}</dd>
                  </div>
                ))}
              </dl>
            </details>
          )}
        </div>
      )}
    </>
  );
}
