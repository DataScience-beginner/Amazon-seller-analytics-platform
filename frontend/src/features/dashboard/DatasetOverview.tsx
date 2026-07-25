import { useCallback, useState, type FormEvent } from 'react';

import {
  fetchCategoryCostEstimate,
  fetchDatasetOverview,
  fetchResearchRanking,
} from '../../api/client';
import type {
  DatasetDistribution,
  DatasetOverview as DatasetOverviewData,
  ResearchRankingSort,
  TargetCostAssumptions,
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

const defaultAssumptions: TargetCostAssumptions = {
  gst_rate_percent: '18',
  amazon_fee_percent: '15',
  shipping_percent: '8',
  advertising_percent: '5',
  returns_percent: '3',
  target_profit_percent: '15',
};

function SubcategoryTables({
  organisationId,
  marketplaceId,
  subcategory,
  importBatchId,
}: {
  organisationId: string;
  marketplaceId: string;
  subcategory: string;
  importBatchId?: string;
}) {
  const [view, setView] = useState<'keepa' | 'cost'>('keepa');
  const [draft, setDraft] = useState(defaultAssumptions);
  const [assumptions, setAssumptions] = useState(defaultAssumptions);
  const [sortBy, setSortBy] = useState<ResearchRankingSort>('research_priority');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');
  const load = useCallback(
    (signal: AbortSignal) =>
      Promise.all([
        fetchResearchRanking(
          organisationId,
          marketplaceId,
          subcategory,
          sortBy,
          sortDirection,
          importBatchId,
          signal,
        ),
        fetchCategoryCostEstimate(
          organisationId,
          marketplaceId,
          subcategory,
          assumptions,
          importBatchId,
          signal,
        ),
      ]),
    [assumptions, importBatchId, marketplaceId, organisationId, sortBy, sortDirection, subcategory],
  );
  const state = useAsync(load);

  function applyAssumptions(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAssumptions(draft);
  }

  return (
    <section className="subcategory-tables" aria-labelledby="subcategory-table-heading">
      <div className="section-heading">
        <div>
          <p className="data-label">Selected subcategory</p>
          <h3 id="subcategory-table-heading">{subcategory}</h3>
        </div>
        <div className="decision-tabs" role="tablist" aria-label="Category table view">
          <button
            role="tab"
            aria-selected={view === 'keepa'}
            type="button"
            onClick={() => setView('keepa')}
          >
            Keepa view
          </button>
          <button
            role="tab"
            aria-selected={view === 'cost'}
            type="button"
            onClick={() => setView('cost')}
          >
            Target sourcing cost
          </button>
        </div>
      </div>

      {view === 'cost' && (
        <form className="assumption-form" onSubmit={applyAssumptions}>
          {(
            [
              ['gst_rate_percent', 'GST'],
              ['amazon_fee_percent', 'Amazon fee'],
              ['shipping_percent', 'Shipping / fulfilment'],
              ['advertising_percent', 'Advertising'],
              ['returns_percent', 'Returns allowance'],
              ['target_profit_percent', 'Target profit'],
            ] as const
          ).map(([name, label]) => (
            <label key={name}>
              <span>{label} %</span>
              <input
                type="number"
                min="0"
                max={name === 'gst_rate_percent' ? '99.99' : '100'}
                step="0.1"
                value={draft[name]}
                onChange={(event) => setDraft({ ...draft, [name]: event.target.value })}
              />
            </label>
          ))}
          <button className="button" type="submit">
            Recalculate
          </button>
          <p>
            Defaults are configurable assumptions. They are not observed Amazon fees or supplier
            quotations.
          </p>
        </form>
      )}

      {state.status === 'loading' && <LoadingState label={`Loading ${subcategory} products…`} />}
      {state.status === 'error' && <ErrorState error={state.error} onRetry={state.retry} />}
      {state.status === 'success' && view === 'keepa' && (
        <>
          <div className="ranking-controls">
            <label>
              Sort products by
              <select
                value={sortBy}
                onChange={(event) => setSortBy(event.target.value as ResearchRankingSort)}
              >
                <option value="research_priority">Research priority</option>
                <option value="demand">Demand</option>
                <option value="price_stability">Price stability</option>
                <option value="competition_quality">Competition quality</option>
                <option value="data_confidence">Data confidence</option>
                <option value="sales_rank_trend">Sales-rank trend</option>
                <option value="buy_box_availability">Buy Box availability</option>
                <option value="monthly_demand">Estimated monthly demand</option>
                <option value="price">Buy Box price</option>
                <option value="offer_count">Seller offers</option>
                <option value="title">Product title</option>
              </select>
            </label>
            <label>
              Direction
              <select
                value={sortDirection}
                onChange={(event) => setSortDirection(event.target.value as 'asc' | 'desc')}
              >
                <option value="desc">Highest first</option>
                <option value="asc">Lowest first</option>
              </select>
            </label>
          </div>
          <details className="ranking-method">
            <summary>How the transparent research ranking works</summary>
            <p>
              Formula {state.data[0].formula_version}. Missing evidence scores zero and is never
              replaced optimistically. Rank remains the product’s position under Research Priority,
              even when this table is sorted by another column.
            </p>
            <ul>
              {Object.entries(state.data[0].weights).map(([name, weight]) => (
                <li key={name}>
                  {name.replaceAll('_', ' ')}: <strong>{weight}%</strong>
                </li>
              ))}
            </ul>
            <small>Configuration: {state.data[0].configuration_checksum.slice(0, 12)}…</small>
          </details>
          <div className="table-scroll" tabIndex={0} aria-label={`${subcategory} ranked products`}>
            <table className="product-table category-product-table ranking-table">
              <thead>
                <tr>
                  <th scope="col">Rank</th>
                  <th scope="col">Product</th>
                  <th scope="col">Priority score</th>
                  <th scope="col">Demand</th>
                  <th scope="col">Stability</th>
                  <th scope="col">Competition</th>
                  <th scope="col">Confidence</th>
                  <th scope="col">Rank trend</th>
                  <th scope="col">Buy Box availability</th>
                  <th scope="col">Seller offers</th>
                  <th scope="col">Buy Box</th>
                </tr>
              </thead>
              <tbody>
                {state.data[0].items.map(({ product, ranking }) => {
                  const component = (id: string) =>
                    ranking.components.find((item) => item.id === id)?.score;
                  return (
                    <tr key={product.id}>
                      <td>
                        <strong>#{ranking.rank}</strong>
                      </td>
                      <td>
                        <div className="product-identity">
                          {product.image_url ? (
                            <img src={product.image_url} alt="" loading="lazy" />
                          ) : (
                            <span className="product-image-placeholder" aria-hidden="true">
                              No image
                            </span>
                          )}
                          <div>
                            <Link to={`/products/${encodeURIComponent(product.id)}`}>
                              {product.title}
                            </Link>
                            <small className="cell-note">
                              {product.asin}
                              {product.amazon_url && (
                                <>
                                  {' · '}
                                  <a href={product.amazon_url} target="_blank" rel="noreferrer">
                                    View on Amazon.in
                                  </a>
                                </>
                              )}
                            </small>
                          </div>
                        </div>
                      </td>
                      <td>
                        <strong>{ranking.score}/100</strong>
                        {ranking.warning_codes.includes('single_seller_control_risk') && (
                          <small className="cell-note">Single-seller control risk</small>
                        )}
                      </td>
                      <td>{formatNumber(component('demand'), 0)}</td>
                      <td>{formatNumber(component('price_stability'), 0)}</td>
                      <td>{formatNumber(component('competition_quality'), 0)}</td>
                      <td>{formatNumber(component('data_confidence'), 0)}</td>
                      <td>{formatNumber(component('sales_rank_trend'), 0)}</td>
                      <td>{formatNumber(component('buy_box_availability'), 0)}</td>
                      <td>{formatNumber(product.offer_count, 0)}</td>
                      <td>{formatMoney(product.buy_box_price)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <small>
            Showing {state.data[0].items.length} of {state.data[0].pagination.total_items} products.
            This is a research rank, not a purchase approval.
          </small>
        </>
      )}
      {state.status === 'success' && view === 'cost' && (
        <>
          <div className="estimate-boundary">
            Calculated from the 90-day average Buy Box price where available. Maximum wholesale cost
            is GST-exclusive; cash outlay includes recoverable input GST.
          </div>
          <div className="table-scroll" tabIndex={0} aria-label={`${subcategory} sourcing costs`}>
            <table className="product-table category-product-table">
              <thead>
                <tr>
                  <th scope="col">Product</th>
                  <th scope="col">Selling price used</th>
                  <th scope="col">Max wholesale ex-GST</th>
                  <th scope="col">Cash outlay incl. GST</th>
                  <th scope="col">Amazon fee</th>
                  <th scope="col">Shipping</th>
                  <th scope="col">Target profit</th>
                </tr>
              </thead>
              <tbody>
                {state.data[1].items.map((product) => {
                  const money = (amount: string | null) =>
                    formatMoney({ amount: amount ?? '', currency_code: product.currency_code });
                  return (
                    <tr key={product.product_id}>
                      <td>
                        <div className="product-identity">
                          {product.image_url && (
                            <img src={product.image_url} alt="" loading="lazy" />
                          )}
                          <div>
                            <Link to={`/products/${encodeURIComponent(product.product_id)}`}>
                              {product.title}
                            </Link>
                            <small className="cell-note">
                              {product.asin}
                              {product.amazon_url && (
                                <>
                                  {' · '}
                                  <a href={product.amazon_url} target="_blank" rel="noreferrer">
                                    View on Amazon.in
                                  </a>
                                </>
                              )}
                            </small>
                          </div>
                        </div>
                      </td>
                      <td>
                        {money(product.selling_price)}
                        <small className="cell-note">
                          {product.selling_price_source === 'buy_box_90d_average'
                            ? '90-day average'
                            : 'Current Buy Box'}
                        </small>
                      </td>
                      <td>{money(product.maximum_wholesale_cost_ex_gst)}</td>
                      <td>{money(product.wholesale_cash_outlay_including_gst)}</td>
                      <td>{money(product.amazon_fee)}</td>
                      <td>{money(product.shipping_allowance)}</td>
                      <td>{money(product.target_profit)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <small>Formula: {state.data[1].formula_version}</small>
        </>
      )}
    </section>
  );
}

function CategoryDeepDive({
  organisationId,
  marketplaceId,
  category,
  importBatchId,
}: {
  organisationId: string;
  marketplaceId: string;
  category: string;
  importBatchId?: string;
}) {
  const [selectedSubcategory, setSelectedSubcategory] = useState<string | null>(null);
  const load = useCallback(
    (signal: AbortSignal) =>
      fetchDatasetOverview(organisationId, marketplaceId, category, importBatchId, signal),
    [category, importBatchId, marketplaceId, organisationId],
  );
  const state = useAsync(load);

  if (state.status === 'loading') return <LoadingState label={`Analysing ${category}…`} />;
  if (state.status === 'error') return <ErrorState error={state.error} onRetry={state.retry} />;
  const overview = state.data;
  const activeSubcategory = selectedSubcategory ?? overview.top_subcategories[0]?.label ?? null;

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
        <DistributionChart
          title={`${category} subcategories`}
          items={overview.top_subcategories}
          onSelect={setSelectedSubcategory}
          selected={activeSubcategory}
        />
        <DistributionChart title={`${category} brands`} items={overview.top_brands} />
        <DistributionChart
          title={`Selling price ranges${overview.price_range_currency_code ? ` (${overview.price_range_currency_code})` : ''}`}
          items={overview.price_ranges}
        />
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

      {activeSubcategory && (
        <SubcategoryTables
          organisationId={organisationId}
          marketplaceId={marketplaceId}
          subcategory={activeSubcategory}
          importBatchId={importBatchId}
        />
      )}
    </section>
  );
}

export function DatasetOverview({
  overview,
  organisationId,
  marketplaceId,
  importBatchId,
}: {
  overview: DatasetOverviewData;
  organisationId: string;
  marketplaceId: string;
  importBatchId?: string;
}) {
  const [selectedCategory, setSelectedCategory] = useState<string | null>(
    overview.category_count === 1 ? (overview.top_categories[0]?.label ?? null) : null,
  );
  const revenueReady = overview.readiness === 'revenue_ready';
  const distribution = overview.top_categories;

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
          title="Largest categories"
          items={distribution}
          onSelect={setSelectedCategory}
          selected={selectedCategory}
        />
        <DistributionChart title="Brand concentration" items={overview.top_brands} />
        <DistributionChart
          title={`Selling price ranges${overview.price_range_currency_code ? ` (${overview.price_range_currency_code})` : ''}`}
          items={overview.price_ranges}
        />
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
          importBatchId={importBatchId}
        />
      )}
    </section>
  );
}
