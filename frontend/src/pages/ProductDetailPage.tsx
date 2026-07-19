import { useCallback } from 'react';

import { fetchProduct } from '../api/client';
import type { Score, Snapshot } from '../api/contracts';
import { Link } from '../app/router';
import { useWorkspace } from '../app/workspace';
import { ErrorState, LoadingState } from '../components/Feedback';
import { PageHeader } from '../components/PageHeader';
import { ScoreDisplay } from '../components/ScoreDisplay';
import { StatusBadge } from '../components/StatusBadge';
import {
  allProductScores,
  productRecommendation,
  productStrategy,
} from '../features/products/productModel';
import { useAsync } from '../hooks/useAsync';
import { formatDate, humanize } from '../utils/format';

function readableMetric(value: unknown): string {
  if (value === null || value === undefined || value === '') return 'Not available';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (typeof value === 'number')
    return new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(value);
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

function snapshotScores(snapshot: Snapshot): Score[] {
  return snapshot.scores ?? [];
}

export function ProductDetailPage({ productId }: { productId: string }) {
  const { selection } = useWorkspace();
  const organisationId = selection.workspace.organisation_id;
  const marketplaceId = selection.marketplace.id;
  const load = useCallback(
    (signal: AbortSignal) => fetchProduct(productId, organisationId, marketplaceId, signal),
    [marketplaceId, organisationId, productId],
  );
  const state = useAsync(load);

  if (state.status === 'loading') return <LoadingState label="Loading product evidence…" />;
  if (state.status === 'error') return <ErrorState error={state.error} onRetry={state.retry} />;

  const product = state.data;
  const recommendation = productRecommendation(product);
  const strategy = productStrategy(product);
  const scores = allProductScores(product);
  const metrics = product.latest_metrics ?? product.metrics ?? {};
  const snapshots = product.snapshots ?? [];
  const supportingStatements = [
    ...(recommendation?.positive_signals ?? []),
    ...(recommendation?.warnings ?? []),
    ...(recommendation?.missing_data ?? []),
    ...(recommendation?.reason_codes ?? []),
  ];
  const showRecommendation = Boolean(recommendation && strategy && supportingStatements.length > 0);

  return (
    <>
      <Link className="back-link" to="/products">
        ← Product opportunities
      </Link>
      <PageHeader
        eyebrow={`${product.brand || 'Unknown brand'} · ${product.asin}`}
        title={product.title ?? 'Untitled product'}
        description={product.category || 'Uncategorised product'}
        action={
          product.amazon_url ? (
            <a
              className="button button--secondary"
              href={product.amazon_url}
              target="_blank"
              rel="noreferrer"
            >
              View Amazon listing
            </a>
          ) : undefined
        }
      />

      {showRecommendation && recommendation && strategy ? (
        <section className="recommendation-hero" aria-labelledby="recommendation-heading">
          <div>
            <p className="data-label">Recommended · advisory only</p>
            <h2 id="recommendation-heading">{humanize(strategy)}</h2>
            <StatusBadge value={strategy} />
          </div>
          <dl>
            <div>
              <dt>Confidence</dt>
              <dd>
                {recommendation.confidence === undefined
                  ? 'Not provided'
                  : `${recommendation.confidence.toFixed(0)} / 100`}
              </dd>
            </div>
            <div>
              <dt>Rule version</dt>
              <dd>{recommendation.formula_version ?? 'Not provided'}</dd>
            </div>
            <div>
              <dt>Latest evidence</dt>
              <dd>{formatDate(product.latest_snapshot_at)}</dd>
            </div>
          </dl>
        </section>
      ) : (
        <section className="panel" aria-labelledby="recommendation-heading">
          <p className="data-label">Recommendation status</p>
          <h2 id="recommendation-heading">No supported recommendation</h2>
          <p className="muted">
            SellerOS does not present a strategy until a persisted recommendation has supporting
            evidence. Review the scores and missing-data notices below.
          </p>
        </section>
      )}

      <section className="panel" aria-labelledby="scores-heading">
        <div className="section-heading">
          <div>
            <p className="data-label">Calculated</p>
            <h2 id="scores-heading">Explainable scores</h2>
          </div>
        </div>
        {scores.length === 0 ? (
          <p className="muted">No scores are available for the latest snapshot.</p>
        ) : (
          <div className="score-grid">
            {scores.map((score) => (
              <div key={score.name}>
                <ScoreDisplay score={score} />
                {score.reason_codes && score.reason_codes.length > 0 && (
                  <ul className="reason-code-list">
                    {score.reason_codes.map((reason, index) => (
                      <li key={`${reason}-${index}`}>{humanize(reason)}</li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      {showRecommendation && recommendation && (
        <div className="evidence-grid">
          <section
            className="panel signal-panel signal-panel--positive"
            aria-labelledby="positive-heading"
          >
            <p className="data-label">Positive evidence</p>
            <h2 id="positive-heading">Signals</h2>
            {recommendation.positive_signals && recommendation.positive_signals.length > 0 ? (
              <ul>
                {recommendation.positive_signals.map((signal) => (
                  <li key={signal}>{signal}</li>
                ))}
              </ul>
            ) : (
              <p className="muted">No positive evidence statements were generated.</p>
            )}
          </section>
          <section
            className="panel signal-panel signal-panel--warning"
            aria-labelledby="warning-heading"
          >
            <p className="data-label">Risk evidence</p>
            <h2 id="warning-heading">Warnings</h2>
            {recommendation.warnings && recommendation.warnings.length > 0 ? (
              <ul>
                {recommendation.warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            ) : (
              <p className="muted">No warning statements were generated.</p>
            )}
          </section>
          <section
            className="panel signal-panel signal-panel--missing"
            aria-labelledby="missing-heading"
          >
            <p className="data-label">Confidence limitations</p>
            <h2 id="missing-heading">Missing data</h2>
            {recommendation.missing_data && recommendation.missing_data.length > 0 ? (
              <ul>
                {recommendation.missing_data.map((notice) => (
                  <li key={notice}>{notice}</li>
                ))}
              </ul>
            ) : (
              <p className="muted">No missing-data notices were generated.</p>
            )}
          </section>
        </div>
      )}

      {recommendation && !showRecommendation && (
        <div className="form-message form-message--warning" role="status">
          A recommendation record was withheld because explanatory evidence is unavailable.
        </div>
      )}

      <section className="panel" aria-labelledby="metrics-heading">
        <div className="section-heading">
          <div>
            <p className="data-label">Observed</p>
            <h2 id="metrics-heading">Latest market metrics</h2>
          </div>
        </div>
        {Object.keys(metrics).length === 0 ? (
          <p className="muted">No market metrics are available.</p>
        ) : (
          <dl className="metric-grid">
            {Object.entries(metrics).map(([name, value]) => (
              <div key={name}>
                <dt>{humanize(name)}</dt>
                <dd>{readableMetric(value)}</dd>
              </div>
            ))}
          </dl>
        )}
      </section>

      <section className="panel" aria-labelledby="history-heading">
        <div className="section-heading">
          <div>
            <p className="data-label">Immutable history</p>
            <h2 id="history-heading">Snapshot and strategy history</h2>
          </div>
        </div>
        {snapshots.length === 0 ? (
          <p className="muted">No historical snapshots are available.</p>
        ) : (
          <div
            className="table-scroll"
            tabIndex={0}
            aria-label="Scrollable product snapshot history"
          >
            <table>
              <thead>
                <tr>
                  <th scope="col">Captured</th>
                  <th scope="col">Recommendation</th>
                  <th scope="col">Overall score</th>
                  <th scope="col">Formula</th>
                </tr>
              </thead>
              <tbody>
                {snapshots.map((snapshot) => {
                  const overall = snapshotScores(snapshot).find(
                    (score) => score.name === 'overall_opportunity',
                  );
                  return (
                    <tr key={snapshot.id}>
                      <td>{formatDate(snapshot.captured_at ?? snapshot.snapshot_at)}</td>
                      <td>
                        {snapshot.recommendation ? (
                          <StatusBadge value={snapshot.recommendation.strategy} />
                        ) : (
                          'Not available'
                        )}
                      </td>
                      <td>{overall ? `${overall.value.toFixed(0)} / 100` : 'Not available'}</td>
                      <td>
                        {snapshot.recommendation?.formula_version ??
                          overall?.formula_version ??
                          'Not available'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {product.raw_attributes && Object.keys(product.raw_attributes).length > 0 && (
        <details className="panel raw-attributes">
          <summary>Preserved source fields</summary>
          <dl className="metric-grid">
            {Object.entries(product.raw_attributes).map(([name, value]) => (
              <div key={name}>
                <dt>{name}</dt>
                <dd>{readableMetric(value)}</dd>
              </div>
            ))}
          </dl>
        </details>
      )}
    </>
  );
}
