import { useCallback, useMemo, type FormEvent } from 'react';

import { fetchProducts } from '../api/client';
import type { ProductQuery } from '../api/contracts';
import { Link, useLocation, useNavigate } from '../app/router';
import { useWorkspace } from '../app/workspace';
import { EmptyState, ErrorState, LoadingState } from '../components/Feedback';
import { PageHeader } from '../components/PageHeader';
import { StatusBadge } from '../components/StatusBadge';
import { productScore, productStrategy } from '../features/products/productModel';
import { useAsync } from '../hooks/useAsync';
import { formatDate, formatMoney, formatNumber, humanize } from '../utils/format';

const strategies = [
  'discovery',
  'test_buy',
  'growth',
  'cash_cow',
  'premium_margin',
  'monitor',
  'clearance_watch',
  'avoid',
];

const filterNames = [
  'search',
  'strategy',
  'category',
  'min_score',
  'max_score',
  'min_offer_count',
  'max_offer_count',
  'min_price',
  'max_price',
  'min_confidence',
  'max_confidence',
  'sort_by',
  'sort_direction',
  'page',
  'page_size',
  'columns',
] as const;

const configurableColumns = [
  { key: 'recommendation', label: 'Recommendation' },
  { key: 'overall', label: 'Overall score' },
  { key: 'confidence', label: 'Data confidence' },
  { key: 'offers', label: 'Offer count' },
  { key: 'price', label: 'Observed price' },
  { key: 'snapshot', label: 'Latest snapshot' },
] as const;

type ConfigurableColumn = (typeof configurableColumns)[number]['key'];
const configurableColumnKeys = new Set<ConfigurableColumn>(
  configurableColumns.map((column) => column.key),
);

function valuesFrom(searchParams: URLSearchParams): Record<(typeof filterNames)[number], string> {
  return Object.fromEntries(
    filterNames.map((name) => [name, searchParams.get(name) ?? '']),
  ) as Record<(typeof filterNames)[number], string>;
}

function paramsFromForm(form: HTMLFormElement): URLSearchParams {
  const data = new FormData(form);
  const params = new URLSearchParams();
  filterNames.forEach((name) => {
    if (name === 'page') return;
    if (name === 'columns') {
      const columns = data
        .getAll(name)
        .filter((value): value is string => typeof value === 'string' && value.length > 0);
      params.set(name, columns.length > 0 ? columns.join(',') : 'none');
      return;
    }
    const value = data.get(name);
    if (typeof value === 'string' && value.trim()) params.set(name, value.trim());
  });
  params.set('page', '1');
  return params;
}

function visibleColumns(value: string): Set<ConfigurableColumn> {
  if (!value) return new Set(configurableColumnKeys);
  if (value === 'none') return new Set();
  return new Set(
    value
      .split(',')
      .filter((column): column is ConfigurableColumn =>
        configurableColumnKeys.has(column as ConfigurableColumn),
      ),
  );
}

export function ProductsPage() {
  const { selection } = useWorkspace();
  const location = useLocation();
  const navigate = useNavigate();
  const values = useMemo(() => valuesFrom(location.searchParams), [location.search]);
  const organisationId = selection.workspace.organisation_id;
  const marketplaceId = selection.marketplace.id;
  const query = useMemo<ProductQuery>(
    () => ({
      organisation_id: organisationId,
      marketplace_id: marketplaceId,
      ...Object.fromEntries(
        Object.entries(values).filter(([name, value]) => name !== 'columns' && value !== ''),
      ),
      page: values.page || '1',
      page_size: values.page_size || '25',
      sort_by: values.sort_by || 'overall_opportunity',
      sort_direction: values.sort_direction || 'desc',
    }),
    [marketplaceId, organisationId, values],
  );
  const load = useCallback((signal: AbortSignal) => fetchProducts(query, signal), [query]);
  const state = useAsync(load);

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    navigate(`/products?${paramsFromForm(event.currentTarget).toString()}`);
  }

  function goToPage(page: number) {
    const params = new URLSearchParams(location.searchParams);
    params.set('page', String(page));
    navigate(`/products?${params.toString()}`);
  }

  const result = state.status === 'success' ? state.data : null;
  const totalPages = result
    ? (result.total_pages ?? Math.max(1, Math.ceil(result.total / result.page_size)))
    : 1;
  const strategyOptions = Array.from(
    new Set(
      [values.strategy, ...strategies, ...(result?.available_filters?.strategies ?? [])].filter(
        Boolean,
      ),
    ),
  );
  const shownColumns = visibleColumns(values.columns);
  const hasFilters = filterNames.some(
    (name) =>
      !['page', 'page_size', 'sort_by', 'sort_direction', 'columns'].includes(name) && values[name],
  );

  return (
    <>
      <PageHeader
        eyebrow="Portfolio intelligence"
        title="Product opportunities"
        description="Search observed product evidence and compare explainable recommendations. All sorting and filtering is applied server-side."
      />

      <form className="panel filters-panel" onSubmit={applyFilters} key={location.search}>
        <div className="filters-primary">
          <label className="field field--search">
            <span>Search products</span>
            <input
              name="search"
              type="search"
              defaultValue={values.search}
              placeholder="ASIN, title or brand"
            />
          </label>
          <label className="field">
            <span>Strategy</span>
            <select name="strategy" defaultValue={values.strategy}>
              <option value="">All strategies</option>
              {strategyOptions.map((strategy) => (
                <option value={strategy} key={strategy}>
                  {humanize(strategy)}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Category</span>
            <input name="category" defaultValue={values.category} placeholder="All categories" />
          </label>
        </div>

        <details className="advanced-filters">
          <summary>Score, offer, price and confidence filters</summary>
          <div className="filter-range-grid">
            <fieldset>
              <legend>Overall score</legend>
              <label className="field">
                <span>Minimum</span>
                <input
                  name="min_score"
                  type="number"
                  min="0"
                  max="100"
                  defaultValue={values.min_score}
                />
              </label>
              <label className="field">
                <span>Maximum</span>
                <input
                  name="max_score"
                  type="number"
                  min="0"
                  max="100"
                  defaultValue={values.max_score}
                />
              </label>
            </fieldset>
            <fieldset>
              <legend>Offer count</legend>
              <label className="field">
                <span>Minimum</span>
                <input
                  name="min_offer_count"
                  type="number"
                  min="0"
                  defaultValue={values.min_offer_count}
                />
              </label>
              <label className="field">
                <span>Maximum</span>
                <input
                  name="max_offer_count"
                  type="number"
                  min="0"
                  defaultValue={values.max_offer_count}
                />
              </label>
            </fieldset>
            <fieldset>
              <legend>Observed price</legend>
              <label className="field">
                <span>Minimum</span>
                <input
                  name="min_price"
                  type="number"
                  min="0"
                  step="0.01"
                  defaultValue={values.min_price}
                />
              </label>
              <label className="field">
                <span>Maximum</span>
                <input
                  name="max_price"
                  type="number"
                  min="0"
                  step="0.01"
                  defaultValue={values.max_price}
                />
              </label>
            </fieldset>
            <fieldset>
              <legend>Data confidence</legend>
              <label className="field">
                <span>Minimum</span>
                <input
                  name="min_confidence"
                  type="number"
                  min="0"
                  max="100"
                  defaultValue={values.min_confidence}
                />
              </label>
              <label className="field">
                <span>Maximum</span>
                <input
                  name="max_confidence"
                  type="number"
                  min="0"
                  max="100"
                  defaultValue={values.max_confidence}
                />
              </label>
            </fieldset>
          </div>
        </details>

        <details className="advanced-filters">
          <summary>Choose table columns</summary>
          <fieldset className="column-picker">
            <legend>Visible evidence columns</legend>
            {configurableColumns.map((column) => (
              <label key={column.key}>
                <input
                  type="checkbox"
                  name="columns"
                  value={column.key}
                  defaultChecked={shownColumns.has(column.key)}
                />
                <span>{column.label}</span>
              </label>
            ))}
          </fieldset>
        </details>

        <div className="filter-footer">
          <label className="field">
            <span>Sort by</span>
            <select name="sort_by" defaultValue={values.sort_by || 'overall_opportunity'}>
              <option value="overall_opportunity">Overall opportunity</option>
              <option value="data_confidence">Data confidence</option>
              <option value="price">Observed price</option>
              <option value="offer_count">Offer count</option>
              <option value="snapshot_at">Latest snapshot</option>
              <option value="asin">ASIN</option>
              <option value="title">Title</option>
              <option value="brand">Brand</option>
              <option value="category">Category</option>
              <option value="strategy">Strategy</option>
            </select>
          </label>
          <label className="field">
            <span>Direction</span>
            <select name="sort_direction" defaultValue={values.sort_direction || 'desc'}>
              <option value="desc">Highest first</option>
              <option value="asc">Lowest first</option>
            </select>
          </label>
          <label className="field field--compact">
            <span>Rows</span>
            <select name="page_size" defaultValue={values.page_size || '25'}>
              <option value="10">10</option>
              <option value="25">25</option>
              <option value="50">50</option>
            </select>
          </label>
          <button className="button" type="submit">
            Apply filters
          </button>
          {hasFilters && (
            <Link className="button button--ghost" to="/products">
              Clear filters
            </Link>
          )}
        </div>
      </form>

      {state.status === 'loading' && <LoadingState label="Loading product opportunities…" />}
      {state.status === 'error' && <ErrorState error={state.error} onRetry={state.retry} />}
      {result && result.items.length === 0 && (
        <EmptyState
          title={hasFilters ? 'No products match these filters' : 'No products have been imported'}
          action={
            hasFilters ? (
              <Link className="button button--secondary" to="/products">
                Clear filters
              </Link>
            ) : (
              <Link className="button" to="/imports">
                Upload Keepa data
              </Link>
            )
          }
        >
          <p>
            {hasFilters
              ? 'Broaden the score, price or strategy criteria and try again.'
              : 'Your product opportunity table will appear after the first confirmed import.'}
          </p>
        </EmptyState>
      )}
      {result && result.items.length > 0 && (
        <section className="panel results-panel" aria-labelledby="results-heading">
          <div className="section-heading">
            <div>
              <p className="data-label">Observed and calculated</p>
              <h2 id="results-heading">{formatNumber(result.total, 0)} products</h2>
            </div>
            <span>
              Page {result.page} of {totalPages}
            </span>
          </div>
          <div
            className="table-scroll"
            tabIndex={0}
            aria-label="Scrollable product opportunity table"
          >
            <table className="product-table">
              <thead>
                <tr>
                  <th scope="col">Product</th>
                  {shownColumns.has('recommendation') && <th scope="col">Recommendation</th>}
                  {shownColumns.has('overall') && <th scope="col">Overall</th>}
                  {shownColumns.has('confidence') && <th scope="col">Confidence</th>}
                  {shownColumns.has('offers') && <th scope="col">Offers</th>}
                  {shownColumns.has('price') && <th scope="col">Observed price</th>}
                  {shownColumns.has('snapshot') && <th scope="col">Latest snapshot</th>}
                </tr>
              </thead>
              <tbody>
                {result.items.map((product) => {
                  const overall = productScore(product, 'overall_opportunity');
                  const confidence = productScore(product, 'data_confidence');
                  const strategy = productStrategy(product);
                  return (
                    <tr key={product.id}>
                      <td>
                        <div className="product-identity">
                          {product.image_url && (
                            <img src={product.image_url} alt="" loading="lazy" />
                          )}
                          <div>
                            <Link to={`/products/${encodeURIComponent(product.id)}`}>
                              {product.title}
                            </Link>
                            <small>
                              {product.brand || 'Unknown brand'} · {product.asin}
                            </small>
                          </div>
                        </div>
                      </td>
                      {shownColumns.has('recommendation') && (
                        <td>{strategy ? <StatusBadge value={strategy} /> : 'Not available'}</td>
                      )}
                      {shownColumns.has('overall') && (
                        <td>{overall ? `${formatNumber(overall.value)} / 100` : '—'}</td>
                      )}
                      {shownColumns.has('confidence') && (
                        <td>{confidence ? `${formatNumber(confidence.value)} / 100` : '—'}</td>
                      )}
                      {shownColumns.has('offers') && (
                        <td>{formatNumber(product.offer_count, 0)}</td>
                      )}
                      {shownColumns.has('price') && <td>{formatMoney(product.buy_box_price)}</td>}
                      {shownColumns.has('snapshot') && (
                        <td>{formatDate(product.latest_snapshot_at)}</td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <nav className="pagination" aria-label="Product result pages">
            <button
              className="button button--secondary"
              type="button"
              disabled={result.page <= 1}
              onClick={() => goToPage(result.page - 1)}
            >
              Previous
            </button>
            <span aria-live="polite">
              Page {result.page} of {totalPages}
            </span>
            <button
              className="button button--secondary"
              type="button"
              disabled={result.page >= totalPages}
              onClick={() => goToPage(result.page + 1)}
            >
              Next
            </button>
          </nav>
        </section>
      )}
    </>
  );
}
