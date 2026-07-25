import { useCallback, useState } from 'react';

import { fetchDatasetOverview, fetchProducts } from '../../api/client';
import type {
  DatasetDistribution,
  DatasetOverview as DatasetOverviewData,
} from '../../api/contracts';
import { Link } from '../../app/router';
import { ErrorState, LoadingState } from '../../components/Feedback';
import { useAsync } from '../../hooks/useAsync';
import { formatMoney, formatNumber } from '../../utils/format';

function percentage(value: number | string): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Math.max(0, Math.min(100, parsed)) : 0;
}

function DistributionChart({
  title,
  items,
  onSelect,
  selected,
}: {
  title: string;
  items: DatasetDistribution[];
  onSelect?: (label: string) => void;
  selected?: string | null;
}) {
  const maximum = Math.max(...items.map((item) => item.product_count), 1);
  return (
    <section className="dataset-chart" aria-label={title}>
      <h3>{title}</h3>
      <div className="dataset-bars">
        {items.map((item) => (
          <div className="dataset-bar" key={item.label}>
            {onSelect ? (
              <button
                className={selected === item.label ? 'dataset-category--active' : ''}
                type="button"
                onClick={() => onSelect(item.label)}
              >
                {item.label}
              </button>
            ) : (
              <span title={item.label}>{item.label}</span>
            )}
            <div aria-hidden="true">
              <i style={{ width: `${(item.product_count / maximum) * 100}%` }} />
            </div>
            <strong>{formatNumber(item.product_count, 0)}</strong>
            <small>{formatNumber(percentage(item.product_percentage))}%</small>
          </div>
        ))}
      </div>
    </section>
  );
}

function CategoryDeepDive({
  organisationId,
  marketplaceId,
  category,
}: {
  organisationId: string;
  marketplaceId: string;
  category: string;
}) {
  const load = useCallback(
    (signal: AbortSignal) =>
      Promise.all([
        fetchDatasetOverview(organisationId, marketplaceId, category, signal),
        fetchProducts(
          {
            organisation_id: organisationId,
            marketplace_id: marketplaceId,
            category,
            screen: 'all',
            sort_by: 'overall_opportunity',
            sort_direction: 'desc',
            page: '1',
            page_size: '10',
          },
          signal,
        ),
      ]),
    [category, marketplaceId, organisationId],
  );
  const state = useAsync(load);

  if (state.status === 'loading') return <LoadingState label={`Analysing ${category}…`} />;
  if (state.status === 'error') return <ErrorState error={state.error} onRetry={state.retry} />;
  const [overview, products] = state.data;

  return (
    <section className="category-deep-dive" aria-labelledby="category-deep-dive-heading">
      <div className="section-heading">
        <div>
          <p className="data-label">Selected category</p>
          <h2 id="category-deep-dive-heading">{category}</h2>
          <p>
            {formatNumber(overview.product_count, 0)} products ·{' '}
            {formatNumber(overview.subcategory_count, 0)} subcategories ·{' '}
            {formatNumber(overview.brand_count, 0)} brands
          </p>
        </div>
        <Link
          to={`/products?screen=all&category=${encodeURIComponent(category)}&sort_by=overall_opportunity&sort_direction=desc`}
        >
          Open full category research
        </Link>
      </div>

      <div className="dataset-panel-grid">
        <DistributionChart title={`${category} subcategories`} items={overview.top_subcategories} />
        <DistributionChart title={`${category} brands`} items={overview.top_brands} />
        <section className="dataset-chart" aria-label={`${category} evidence coverage`}>
          <h3>Category evidence coverage</h3>
          <div className="coverage-bars">
            {overview.coverage.map((item) => {
              const value = percentage(item.coverage_percentage);
              return (
                <div key={item.id}>
                  <span>{item.label}</span>
                  <div aria-hidden="true">
                    <i
                      className={value < 70 ? 'coverage-low' : ''}
                      style={{ width: `${value}%` }}
                    />
                  </div>
                  <strong>{formatNumber(value)}%</strong>
                </div>
              );
            })}
          </div>
        </section>
      </div>

      <div className="table-scroll" tabIndex={0} aria-label={`${category} ranked products`}>
        <table className="product-table category-product-table">
          <thead>
            <tr>
              <th scope="col">Product</th>
              <th scope="col">Brand</th>
              <th scope="col">Buy Box</th>
              <th scope="col">Seller offers</th>
              <th scope="col">Demand</th>
              <th scope="col">Confidence</th>
            </tr>
          </thead>
          <tbody>
            {products.items.map((product) => (
              <tr key={product.id}>
                <td>
                  <Link to={`/products/${encodeURIComponent(product.id)}`}>{product.title}</Link>
                  <small className="cell-note">{product.asin}</small>
                </td>
                <td>{product.brand || 'Unknown'}</td>
                <td>{formatMoney(product.buy_box_price)}</td>
                <td>{formatNumber(product.offer_count, 0)}</td>
                <td>{formatNumber(product.demand_score, 0)}</td>
                <td>{formatNumber(product.confidence_score, 0)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function DatasetOverview({
  overview,
  organisationId,
  marketplaceId,
}: {
  overview: DatasetOverviewData;
  organisationId: string;
  marketplaceId: string;
}) {
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const revenueReady = overview.readiness === 'revenue_ready';
  const distribution =
    overview.category_count === 1 ? overview.top_subcategories : overview.top_categories;

  return (
    <section className="dataset-overview" aria-labelledby="dataset-overview-heading">
      <div className={`dataset-readiness dataset-readiness--${overview.readiness}`}>
        <div>
          <p className="data-label">Dataset decision readiness</p>
          <h2 id="dataset-overview-heading">{overview.readiness_title}</h2>
          <p>{overview.readiness_message}</p>
        </div>
        <strong>
          {formatNumber(percentage(overview.monthly_demand_coverage_percentage))}% demand coverage
        </strong>
      </div>

      <div className="dataset-stat-grid">
        <article>
          <span>Products</span>
          <strong>{formatNumber(overview.product_count, 0)}</strong>
        </article>
        <article>
          <span>Categories</span>
          <strong>{formatNumber(overview.category_count, 0)}</strong>
        </article>
        <article>
          <span>Subcategories</span>
          <strong>{formatNumber(overview.subcategory_count, 0)}</strong>
        </article>
        <article>
          <span>Brands</span>
          <strong>{formatNumber(overview.brand_count, 0)}</strong>
        </article>
        <article className={revenueReady ? '' : 'dataset-stat--blocked'}>
          <span>Estimated monthly revenue</span>
          <strong>
            {revenueReady
              ? formatMoney({
                  amount: overview.estimated_monthly_revenue ?? 0,
                  currency_code: overview.currency_code,
                })
              : 'Not responsible to calculate'}
          </strong>
        </article>
      </div>

      <div className="dataset-panel-grid">
        <section className="dataset-chart" aria-label="Evidence coverage">
          <h3>Evidence coverage</h3>
          <div className="coverage-bars">
            {overview.coverage.map((item) => {
              const value = percentage(item.coverage_percentage);
              return (
                <div key={item.id}>
                  <span>{item.label}</span>
                  <div aria-hidden="true">
                    <i
                      className={value < 70 ? 'coverage-low' : ''}
                      style={{ width: `${value}%` }}
                    />
                  </div>
                  <strong>{formatNumber(value)}%</strong>
                </div>
              );
            })}
          </div>
        </section>
        <DistributionChart
          title={overview.category_count === 1 ? 'Largest subcategories' : 'Largest categories'}
          items={distribution}
          onSelect={overview.category_count === 1 ? undefined : setSelectedCategory}
          selected={selectedCategory}
        />
        <DistributionChart title="Brand concentration" items={overview.top_brands} />
      </div>

      <div className="dataset-conclusion">
        <strong>Broad conclusion</strong>
        {overview.conclusion_codes.includes('revenue_blocked_low_monthly_demand') && (
          <p>
            Use rank, price, reviews and seller offers for relative research. Revenue remains hidden
            until at least 70% of products have both monthly-demand and price evidence.
          </p>
        )}
        {overview.conclusion_codes.includes('brand_concentration_requires_review') && (
          <p>
            One brand represents at least 10% of this dataset. Treat authorisation, authenticity and
            sourcing evidence as mandatory checks.
          </p>
        )}
        {overview.conclusion_codes.includes('single_root_category_dataset') && (
          <p>
            This is a focused single-category dataset; compare its subcategories before products.
          </p>
        )}
      </div>
      {selectedCategory && (
        <CategoryDeepDive
          organisationId={organisationId}
          marketplaceId={marketplaceId}
          category={selectedCategory}
        />
      )}
    </section>
  );
}
