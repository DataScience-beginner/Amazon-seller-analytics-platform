import { useCallback, useMemo, type FormEvent } from 'react';

import { fetchProducts } from '../api/client';
import type { ProductQuery, ResearchScreen } from '../api/contracts';
import { Link, useLocation, useNavigate } from '../app/router';
import { useWorkspace } from '../app/workspace';
import { EmptyState, ErrorState, LoadingState } from '../components/Feedback';
import { PageHeader } from '../components/PageHeader';
import {
  BrandLabel,
  ResearchCharts,
  ResearchStatusLabel,
} from '../features/research/ResearchCharts';
import { useAsync } from '../hooks/useAsync';
import { formatMoney, formatNumber } from '../utils/format';

const defaultScreen = 'priority_research';
const filterNames = [
  'screen',
  'search',
  'brand_classification',
  'category',
  'max_offer_count',
  'min_price',
  'max_price',
  'sort_by',
  'sort_direction',
  'page',
  'page_size',
] as const;

type FilterName = (typeof filterNames)[number];

function valuesFrom(searchParams: URLSearchParams): Record<FilterName, string> {
  return Object.fromEntries(
    filterNames.map((name) => [name, searchParams.get(name) ?? '']),
  ) as Record<FilterName, string>;
}

function paramsFromForm(form: HTMLFormElement): URLSearchParams {
  const data = new FormData(form);
  const params = new URLSearchParams();
  filterNames.forEach((name) => {
    if (name === 'page') return;
    const value = data.get(name);
    if (typeof value === 'string' && value.trim()) params.set(name, value.trim());
  });
  params.set('page', '1');
  return params;
}

function screenHref(searchParams: URLSearchParams, screen: string): string {
  const next = new URLSearchParams(searchParams);
  next.set('screen', screen);
  next.set('page', '1');
  return `/products?${next.toString()}`;
}

function fallbackScreens(): ResearchScreen[] {
  return [
    {
      id: 'priority_research',
      label: 'Priority research',
      description: 'The strongest market-evidence candidates for supplier and permission checks.',
    },
    {
      id: 'promising',
      label: 'Promising',
      description: 'Broader thresholds for manual product investigation.',
    },
    {
      id: 'low_competition',
      label: 'Low seller competition',
      description: 'Few current offers and an approachable competition score.',
    },
    {
      id: 'stable_pricing',
      label: 'Stable pricing',
      description: 'Products with high price-stability evidence.',
    },
    {
      id: 'needs_evidence',
      label: 'Needs evidence',
      description: 'Low-confidence products blocked from sourcing decisions.',
    },
    {
      id: 'all',
      label: 'All products',
      description: 'The complete imported product universe.',
    },
  ];
}

export function ProductsPage() {
  const { selection } = useWorkspace();
  const location = useLocation();
  const navigate = useNavigate();
  const values = useMemo(() => valuesFrom(location.searchParams), [location.search]);
  const activeScreen = values.screen || defaultScreen;
  const organisationId = selection.workspace.organisation_id;
  const marketplaceId = selection.marketplace.id;
  const query = useMemo<ProductQuery>(
    () => ({
      organisation_id: organisationId,
      marketplace_id: marketplaceId,
      screen: activeScreen,
      ...Object.fromEntries(
        Object.entries(values).filter(([name, value]) => name !== 'screen' && value !== ''),
      ),
      page: values.page || '1',
      page_size: values.page_size || '25',
      sort_by: values.sort_by || 'overall_opportunity',
      sort_direction: values.sort_direction || 'desc',
    }),
    [activeScreen, marketplaceId, organisationId, values],
  );
  const load = useCallback((signal: AbortSignal) => fetchProducts(query, signal), [query]);
  const state = useAsync(load);

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    navigate(`/products?${paramsFromForm(event.currentTarget).toString()}`);
  }

  function goToPage(page: number) {
    const params = new URLSearchParams(location.searchParams);
    params.set('screen', activeScreen);
    params.set('page', String(page));
    navigate(`/products?${params.toString()}`);
  }

  const result = state.status === 'success' ? state.data : null;
  const totalPages =
    result?.total_pages ?? (result ? Math.max(1, Math.ceil(result.total / result.page_size)) : 1);
  const screens = result?.screens ?? fallbackScreens();
  const hasNarrowingFilters = Boolean(
    values.search ||
    values.brand_classification ||
    values.category ||
    values.max_offer_count ||
    values.min_price ||
    values.max_price,
  );

  return (
    <>
      <PageHeader
        eyebrow="Product research"
        title="Research screener"
        description="Reduce the imported product universe to explainable market candidates. Priority research is not a buy approval: validate brand permission, supplier cost and Amazon fees next."
      />

      <section className="research-screen-grid" aria-label="Product research strategies">
        {screens.map((screen) => (
          <Link
            key={screen.id}
            to={screenHref(location.searchParams, screen.id)}
            className={`research-screen ${activeScreen === screen.id ? 'research-screen--active' : ''}`}
            aria-current={activeScreen === screen.id ? 'page' : undefined}
          >
            <strong>{screen.label}</strong>
            <span>{screen.description}</span>
          </Link>
        ))}
      </section>

      <form className="panel research-filters" onSubmit={applyFilters} key={location.search}>
        <input type="hidden" name="screen" value={activeScreen} />
        <div className="research-filter-row">
          <label className="field field--search">
            <span>Search ASIN, title or brand</span>
            <input name="search" type="search" defaultValue={values.search} />
          </label>
          <label className="field">
            <span>Brand evidence</span>
            <select name="brand_classification" defaultValue={values.brand_classification}>
              <option value="">All brand types</option>
              <option value="declared_brand">Declared brand</option>
              <option value="likely_generic">Likely generic</option>
              <option value="unknown">Brand unknown</option>
            </select>
          </label>
          <button className="button" type="submit">
            Screen products
          </button>
        </div>

        <details className="advanced-filters">
          <summary>More filters</summary>
          <div className="research-filter-grid">
            <label className="field">
              <span>Category</span>
              <input name="category" defaultValue={values.category} />
            </label>
            <label className="field">
              <span>Maximum seller offers</span>
              <input
                name="max_offer_count"
                type="number"
                min="0"
                defaultValue={values.max_offer_count}
              />
            </label>
            <label className="field">
              <span>Minimum price</span>
              <input name="min_price" type="number" min="0" defaultValue={values.min_price} />
            </label>
            <label className="field">
              <span>Maximum price</span>
              <input name="max_price" type="number" min="0" defaultValue={values.max_price} />
            </label>
            <label className="field">
              <span>Sort by</span>
              <select name="sort_by" defaultValue={values.sort_by || 'overall_opportunity'}>
                <option value="overall_opportunity">Overall opportunity</option>
                <option value="demand">Demand score</option>
                <option value="competition">Competition score</option>
                <option value="price_stability">Price stability</option>
                <option value="data_confidence">Data confidence</option>
                <option value="price">Observed price</option>
                <option value="offer_count">Seller offers</option>
                <option value="observed_on">Dataset date</option>
              </select>
            </label>
            <label className="field">
              <span>Direction</span>
              <select name="sort_direction" defaultValue={values.sort_direction || 'desc'}>
                <option value="desc">Highest first</option>
                <option value="asc">Lowest first</option>
              </select>
            </label>
            <label className="field">
              <span>Rows per page</span>
              <select name="page_size" defaultValue={values.page_size || '25'}>
                <option value="10">10</option>
                <option value="25">25</option>
                <option value="50">50</option>
              </select>
            </label>
          </div>
        </details>

        {hasNarrowingFilters && (
          <Link
            className="button button--ghost"
            to={`/products?screen=${encodeURIComponent(activeScreen)}`}
          >
            Clear extra filters
          </Link>
        )}
      </form>

      {state.status === 'loading' && <LoadingState label="Screening product evidence…" />}
      {state.status === 'error' && <ErrorState error={state.error} onRetry={state.retry} />}
      {result && result.items.length === 0 && (
        <EmptyState
          title="No products match this research screen"
          action={
            <Link className="button button--secondary" to="/products?screen=all">
              View all products
            </Link>
          }
        >
          <p>Choose a broader screen or remove the additional brand, category or price filters.</p>
        </EmptyState>
      )}

      {result && result.items.length > 0 && (
        <>
          <ResearchCharts products={result.items} />
          <section className="panel results-panel" aria-labelledby="research-results-heading">
            <div className="section-heading">
              <div>
                <p className="data-label">Observed, estimated and calculated evidence</p>
                <h2 id="research-results-heading">
                  {formatNumber(result.total, 0)} matching products
                </h2>
              </div>
              <span>
                Page {result.page} of {totalPages}
              </span>
            </div>
            <div className="research-disclaimer">
              <strong>Decision boundary:</strong> shortlist for research only. Profitability,
              supplier availability and resale authorisation are not yet confirmed.
            </div>
            <div
              className="table-scroll"
              tabIndex={0}
              aria-label="Scrollable product research results"
            >
              <table className="product-table research-table">
                <thead>
                  <tr>
                    <th scope="col">Product</th>
                    <th scope="col">Research action</th>
                    <th scope="col">Brand</th>
                    <th scope="col">Demand</th>
                    <th scope="col">Competition</th>
                    <th scope="col">Est. bought/month</th>
                    <th scope="col">Seller offers</th>
                    <th scope="col">Buy Box</th>
                    <th scope="col">Stability</th>
                    <th scope="col">Confidence</th>
                  </tr>
                </thead>
                <tbody>
                  {result.items.map((product) => (
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
                            <small>{product.asin}</small>
                          </div>
                        </div>
                      </td>
                      <td>
                        {product.research ? (
                          <ResearchStatusLabel status={product.research.status} />
                        ) : (
                          'Unavailable'
                        )}
                      </td>
                      <td>
                        {product.research ? (
                          <BrandLabel classification={product.research.brand_classification} />
                        ) : (
                          'Unknown'
                        )}
                        <small className="cell-note">{product.brand || 'No brand value'}</small>
                      </td>
                      <td>{formatNumber(product.demand_score, 0)}</td>
                      <td>{formatNumber(product.competition_score, 0)}</td>
                      <td>
                        {product.estimated_monthly_bought === null ||
                        product.estimated_monthly_bought === undefined
                          ? '—'
                          : formatNumber(product.estimated_monthly_bought, 0)}
                        <small className="cell-note">Estimated by Keepa</small>
                      </td>
                      <td>{formatNumber(product.offer_count, 0)}</td>
                      <td>{formatMoney(product.buy_box_price)}</td>
                      <td>{formatNumber(product.price_stability_score, 0)}</td>
                      <td>{formatNumber(product.confidence_score, 0)}</td>
                    </tr>
                  ))}
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
            <small className="policy-reference">
              Research policy: {result.research_policy_version ?? 'Unavailable'}
            </small>
          </section>
        </>
      )}
    </>
  );
}
