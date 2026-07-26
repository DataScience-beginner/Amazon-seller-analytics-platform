import { useCallback, useMemo, useState, type ChangeEvent } from 'react';

import {
  createCostProfile,
  createSupplierOffer,
  createTestBuyRecommendation,
  fetchProductEconomics,
  fetchProducts,
  fetchSupplierOffers,
} from '../api/client';
import type {
  CreateCostProfileRequest,
  CreateSupplierOfferRequest,
  CreateTestBuyRequest,
  ProductQuery,
} from '../api/contracts';
import { Link, useLocation, useNavigate } from '../app/router';
import { useWorkspace } from '../app/workspace';
import { EmptyState, ErrorState, LoadingState } from '../components/Feedback';
import { PageHeader } from '../components/PageHeader';
import { CostProfileForm } from '../features/economics/CostProfileForm';
import { CostProfileHistory } from '../features/economics/CostProfileHistory';
import { SupplierOfferComparison } from '../features/economics/SupplierOfferComparison';
import { SupplierOfferForm } from '../features/economics/SupplierOfferForm';
import { TestBuyPlanner } from '../features/economics/TestBuyPlanner';
import { UnitEconomicsPanel } from '../features/economics/UnitEconomicsPanel';
import { useAsync } from '../hooks/useAsync';

function PlanningWorkspace({ productId }: { productId: string }) {
  const { selection } = useWorkspace();
  const [revision, setRevision] = useState(0);
  const [offerPage, setOfferPage] = useState(1);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const organisationId = selection.workspace.organisation_id;
  const marketplaceId = selection.marketplace.id;
  const load = useCallback(
    async (signal: AbortSignal) => {
      const [economics, offers] = await Promise.all([
        fetchProductEconomics(productId, organisationId, marketplaceId, signal),
        fetchSupplierOffers(productId, organisationId, marketplaceId, offerPage, signal),
      ]);
      return { economics, offers };
    },
    [marketplaceId, offerPage, organisationId, productId, revision],
  );
  const state = useAsync(load);

  async function saveCostProfile(command: CreateCostProfileRequest) {
    await createCostProfile(organisationId, marketplaceId, command);
    setSuccessMessage(
      'Cost profile saved. Economics were refreshed for the current effective version.',
    );
    setRevision((value) => value + 1);
  }

  async function saveSupplierOffer(command: CreateSupplierOfferRequest) {
    const offer = await createSupplierOffer(organisationId, marketplaceId, command);
    setSuccessMessage('Supplier offer saved and added to the comparison.');
    setOfferPage(1);
    setRevision((value) => value + 1);
    return offer;
  }

  function generateTestBuy(command: CreateTestBuyRequest) {
    return createTestBuyRecommendation(productId, organisationId, marketplaceId, command);
  }

  if (state.status === 'loading') {
    return <LoadingState label="Loading costs, economics and supplier evidence…" />;
  }
  if (state.status === 'error') return <ErrorState error={state.error} onRetry={state.retry} />;

  const { economics, offers } = state.data;
  return (
    <div className="planning-stack">
      {successMessage && (
        <div className="form-message form-message--success" role="status">
          {successMessage}
        </div>
      )}
      <div className="planning-context">
        <div>
          <span>Selected product</span>
          <strong>{economics.product.title || 'Untitled product'}</strong>
          <small>{economics.product.asin}</small>
        </div>
        <Link className="button button--secondary" to={`/products/${productId}`}>
          Review market evidence
        </Link>
      </div>

      <UnitEconomicsPanel economics={economics} />
      <CostProfileHistory
        profileSource={economics.profile_source}
        activeProfile={economics.active_profile}
        history={economics.profile_history}
      />
      <CostProfileForm
        key={productId}
        productId={productId}
        currencyCode={economics.currency_code}
        profilesByScope={economics.profiles_by_scope}
        history={economics.profile_history}
        onCreate={saveCostProfile}
      />

      <SupplierOfferComparison
        offers={offers.items}
        pagination={offers.pagination}
        selectionNote={offers.selection_note}
        onPageChange={setOfferPage}
      />
      <SupplierOfferForm
        key={productId}
        productId={productId}
        currencyCode={economics.currency_code}
        onCreate={saveSupplierOffer}
      />
      <TestBuyPlanner
        key={`${productId}-${offers.pagination.page}-${offers.pagination.total_items}`}
        offers={offers.items}
        currencyCode={economics.currency_code}
        onGenerate={generateTestBuy}
      />
    </div>
  );
}

export function PlanningPage() {
  const { selection } = useWorkspace();
  const location = useLocation();
  const navigate = useNavigate();
  const selectedProductId = location.searchParams.get('product_id') ?? '';
  const organisationId = selection.workspace.organisation_id;
  const marketplaceId = selection.marketplace.id;
  const query = useMemo<ProductQuery>(
    () => ({
      organisation_id: organisationId,
      marketplace_id: marketplaceId,
      page: '1',
      page_size: '100',
      sort_by: 'observed_on',
      sort_direction: 'desc',
    }),
    [marketplaceId, organisationId],
  );
  const loadProducts = useCallback((signal: AbortSignal) => fetchProducts(query, signal), [query]);
  const products = useAsync(loadProducts);

  function selectProduct(event: ChangeEvent<HTMLSelectElement>) {
    const productId = event.target.value;
    navigate(productId ? `/planning?product_id=${encodeURIComponent(productId)}` : '/planning');
  }

  return (
    <>
      <PageHeader
        eyebrow="Unit economics and sourcing"
        title="Planning"
        description="Enter auditable costs, compare supplier commitments and request advisory test-buy scenarios. Calculations remain deterministic; SellerOS never places an order."
      />

      {products.status === 'loading' && <LoadingState label="Loading products for planning…" />}
      {products.status === 'error' && (
        <ErrorState error={products.error} onRetry={products.retry} />
      )}
      {products.status === 'success' && products.data.items.length === 0 && (
        <EmptyState
          title="Import products before planning"
          action={
            <Link className="button" to="/imports">
              Upload Keepa workbook
            </Link>
          }
        >
          Cost profiles and supplier offers must attach to a scoped product. Complete an import to
          begin.
        </EmptyState>
      )}
      {products.status === 'success' && products.data.items.length > 0 && (
        <>
          <section
            className="panel product-planner-picker"
            aria-labelledby="planner-picker-heading"
          >
            <div>
              <p className="data-label">Planning scope</p>
              <h2 id="planner-picker-heading">Choose a product</h2>
              <p className="muted">
                Showing the latest 100 scoped products. You can also open planning directly from a
                product evidence page.
              </p>
            </div>
            <label className="field">
              <span>Product</span>
              <select value={selectedProductId} onChange={selectProduct}>
                <option value="">Select a product</option>
                {selectedProductId &&
                  !products.data.items.some((product) => product.id === selectedProductId) && (
                    <option value={selectedProductId}>
                      Selected product · {selectedProductId}
                    </option>
                  )}
                {products.data.items.map((product) => (
                  <option value={product.id} key={product.id}>
                    {product.asin} · {product.title || 'Untitled product'}
                  </option>
                ))}
              </select>
            </label>
          </section>

          {selectedProductId ? (
            <PlanningWorkspace
              key={`${organisationId}-${marketplaceId}-${selectedProductId}`}
              productId={selectedProductId}
            />
          ) : (
            <EmptyState title="Select a product to plan">
              SellerOS will load its observed price, active effective-dated cost profile, supplier
              offers and traceable profitability outputs.
            </EmptyState>
          )}
        </>
      )}
    </>
  );
}
