import { useCallback, useState } from 'react';

import { fetchDashboard, fetchDatasetOverview, fetchImports } from '../api/client';
import type { DatasetOverview as DatasetOverviewData } from '../api/contracts';
import { Link } from '../app/router';
import { useWorkspace } from '../app/workspace';
import { EmptyState, ErrorState, LoadingState } from '../components/Feedback';
import { PageHeader } from '../components/PageHeader';
import { ProductSummaryRow } from '../components/ProductSummaryRow';
import { StatusBadge } from '../components/StatusBadge';
import { DatasetOverview } from '../features/dashboard/DatasetOverview';
import { useAsync } from '../hooks/useAsync';
import { formatDate, formatMonth, formatNumber, humanize } from '../utils/format';

function DashboardDatasetSection({
  initialOverview,
  organisationId,
  marketplaceId,
}: {
  initialOverview: DatasetOverviewData;
  organisationId: string;
  marketplaceId: string;
}) {
  const [importBatchId, setImportBatchId] = useState('');
  const loadImports = useCallback(
    (signal: AbortSignal) => fetchImports(organisationId, marketplaceId, signal),
    [marketplaceId, organisationId],
  );
  const imports = useAsync(loadImports);
  const loadOverview = useCallback(
    (signal: AbortSignal) =>
      importBatchId
        ? fetchDatasetOverview(organisationId, marketplaceId, undefined, importBatchId, signal)
        : Promise.resolve(initialOverview),
    [importBatchId, initialOverview, marketplaceId, organisationId],
  );
  const overview = useAsync(loadOverview);
  const completedImports =
    imports.status === 'success'
      ? imports.data.items.filter((item) => item.status === 'completed')
      : [];

  return (
    <>
      <section className="dataset-selector" aria-labelledby="dataset-selector-heading">
        <div>
          <p className="data-label">Active product dataset</p>
          <h2 id="dataset-selector-heading">Choose which import to analyse</h2>
          <p>
            Imports remain separate evidence sets. Changing this selection does not delete data.
          </p>
        </div>
        <label>
          <span>Dataset</span>
          <select value={importBatchId} onChange={(event) => setImportBatchId(event.target.value)}>
            <option value="">Combined latest product evidence</option>
            {completedImports.map((item) => (
              <option value={item.id} key={item.id}>
                {item.original_filename ?? item.filename ?? 'Keepa import'} ·{' '}
                {item.observed_on ?? 'date unavailable'} · {formatNumber(item.row_count ?? 0, 0)}{' '}
                rows
              </option>
            ))}
          </select>
        </label>
      </section>
      {overview.status === 'loading' && <LoadingState label="Switching product dataset…" />}
      {overview.status === 'error' && (
        <ErrorState error={overview.error} onRetry={overview.retry} />
      )}
      {overview.status === 'success' && (
        <DatasetOverview
          key={importBatchId || 'combined'}
          overview={overview.data}
          organisationId={organisationId}
          marketplaceId={marketplaceId}
          importBatchId={importBatchId || undefined}
        />
      )}
    </>
  );
}

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
          {state.data.dataset_overview && (
            <DashboardDatasetSection
              initialOverview={state.data.dataset_overview}
              organisationId={organisationId}
              marketplaceId={marketplaceId}
            />
          )}
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
                    <dt>Dataset month</dt>
                    <dd>
                      {state.data.latest_import.period_month
                        ? formatMonth(state.data.latest_import.period_month)
                        : 'Observation date unavailable'}
                    </dd>
                  </div>
                  <div>
                    <dt>Observed on</dt>
                    <dd>
                      {state.data.latest_import.observed_on
                        ? formatDate(state.data.latest_import.observed_on)
                        : 'Observation date unavailable'}
                    </dd>
                  </div>
                  <div>
                    <dt>Revision</dt>
                    <dd>{state.data.latest_import.revision ?? 'Not available'}</dd>
                  </div>
                  <div>
                    <dt>Uploaded</dt>
                    <dd>{formatDate(state.data.latest_import.uploaded_at)}</dd>
                  </div>
                  <div>
                    <dt>Completed</dt>
                    <dd>{formatDate(state.data.latest_import.completed_at)}</dd>
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
