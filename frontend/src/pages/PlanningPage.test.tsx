import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { Workspace } from '../api/contracts';
import { WorkspaceContext } from '../app/workspace';
import { PlanningPage } from './PlanningPage';

const workspace: Workspace = {
  organisation_id: 'org-1',
  organisation_name: 'Acme Sellers',
  marketplaces: [
    {
      id: 'market-1',
      code: 'IN',
      name: 'Amazon India',
      default_currency_code: 'INR',
    },
  ],
};

const productList = {
  scope: { organisation_id: 'org-1', marketplace_id: 'market-1' },
  items: [
    {
      product_id: 'product-1',
      asin: 'B012345678',
      title: 'Travel Mug',
      brand: 'Acme',
      category: 'Kitchen',
      subcategory: 'Drinkware',
      image_url: null,
      amazon_url: null,
      latest_snapshot_id: 'snapshot-1',
      latest_snapshot_at: '2026-07-18T10:00:00Z',
      buy_box_price: '1299.00',
      currency_code: 'INR',
      offer_count: 4,
      overall_opportunity_score: 75,
      data_confidence_score: 82,
      strategy: 'test_buy',
      recommendation_confidence: 82,
      score_formula_version: '1.0.0',
      strategy_rules_version: '1.0.0',
      data_quality_codes: [],
    },
  ],
  pagination: {
    page: 1,
    page_size: 100,
    total_items: 1,
    total_pages: 1,
    has_previous: false,
    has_next: false,
  },
  query: {
    page: 1,
    page_size: 100,
    sort_by: 'observed_on',
    sort_direction: 'desc',
  },
};

const economics = {
  scope: { organisation_id: 'org-1', marketplace_id: 'market-1' },
  product: { product_id: 'product-1', asin: 'B012345678', title: 'Travel Mug' },
  observed_price: {
    amount: '1299.00',
    currency_code: 'INR',
    evidence_label: 'observed',
    source: 'keepa_import',
    source_at: '2026-07-18T10:00:00Z',
    observed_on: '2026-05-26',
  },
  currency_code: 'INR',
  profile_source: null,
  active_profile: null,
  profiles_by_scope: { product: null, marketplace_default: null },
  profile_history: [],
  calculation: {
    formula_version: 'selleros.unit-economics.v1',
    configuration_checksum: 'economics-checksum',
    status: 'calculated',
    decision_label: 'calculated',
    selling_price_tax_basis: 'tax_inclusive',
    inputs: {
      selling_price: '1299.00',
      purchase_cost: '500.00',
      referral_fee_rate_percent: '15.00',
    },
    formulas: {
      landed_cost: 'purchase_cost + freight_cost + prep_cost + packaging_cost',
    },
    outputs: {
      landed_cost: '560.00',
      net_revenue: '1100.85',
      output_gst: '198.15',
      amazon_fees: '230.00',
      contribution_profit: '409.00',
      margin_percent: '31.49',
      roi_percent: '73.04',
      break_even_price: '700.00',
      minimum_acceptable_price: '850.00',
      target_price: '999.00',
    },
    reason_codes: ['ECONOMICS_FEES_ESTIMATED'],
    fee_evidence: {
      status: 'estimated',
      source: 'Seller fee worksheet',
      effective_at: '2026-07-01T00:00:00Z',
    },
  },
  notices: [],
  audit_history: [],
};

const offer = {
  id: 'offer-1',
  product_id: 'product-1',
  supplier: { id: 'supplier-1', name: 'Reliable Supplies' },
  currency_code: 'INR',
  unit_cost: '500.00',
  minimum_order_quantity: 10,
  lead_time_days: 14,
  quotation_date: '2026-07-01',
  valid_until: '2026-08-01',
  notes: 'Packed at source',
  price_tiers: [{ minimum_quantity: 25, unit_cost: '475.00' }],
  created_at: '2026-07-01T08:00:00Z',
  evidence_label: 'user_confirmed',
};

const offers = {
  scope: { organisation_id: 'org-1', marketplace_id: 'market-1' },
  product: { product_id: 'product-1', asin: 'B012345678', title: 'Travel Mug' },
  items: [offer],
  pagination: {
    page: 1,
    page_size: 100,
    total_items: 1,
    total_pages: 1,
    has_previous: false,
    has_next: false,
  },
  comparison_dimensions: ['unit_cost', 'minimum_order_quantity', 'lead_time_days'],
  selection_note:
    'Price alone does not determine the best offer. Review MOQ and lead time before choosing.',
};

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

function renderPlanning() {
  const marketplace = workspace.marketplaces[0];
  if (!marketplace) throw new Error('Fixture requires a marketplace');
  return render(
    <WorkspaceContext.Provider
      value={{
        workspaces: [workspace],
        selection: { workspace, marketplace },
        select: vi.fn(),
        addWorkspace: vi.fn(),
      }}
    >
      <PlanningPage />
    </WorkspaceContext.Provider>,
  );
}

function baseFetch(options?: {
  onCostProfile?: (body: Record<string, unknown>) => Response;
  onSupplierOffer?: (body: Record<string, unknown>) => Response;
  onScenario?: (body: Record<string, unknown>) => Response;
  onOffers?: (url: string) => Response;
}) {
  return vi.fn(async (input: RequestInfo | URL, request?: RequestInit) => {
    const url = String(input);
    if (url.includes('/products?')) return json(productList);
    if (url.includes('/products/product-1/economics?')) return json(economics);
    if (url.includes('/products/product-1/supplier-offers?')) {
      return options?.onOffers?.(url) ?? json(offers);
    }
    if (url.includes('/cost-profiles?') && request?.method === 'POST') {
      return options?.onCostProfile?.(JSON.parse(String(request.body))) ?? json({}, 201);
    }
    if (url.includes('/supplier-offers?') && request?.method === 'POST') {
      return options?.onSupplierOffer?.(JSON.parse(String(request.body))) ?? json(offer, 201);
    }
    if (url.includes('/products/product-1/test-buy-scenarios?')) {
      return (
        options?.onScenario?.(JSON.parse(String(request?.body))) ??
        json({ message: 'Scenario fixture missing' }, 500)
      );
    }
    throw new Error(`Unexpected request: ${url}`);
  });
}

describe('PlanningPage', () => {
  beforeEach(() => window.history.replaceState({}, '', '/planning?product_id=product-1'));

  it('shows traceable economics, supplier context and server-generated test-buy scenarios', async () => {
    let scenarioBody: Record<string, unknown> | undefined;
    vi.stubGlobal(
      'fetch',
      baseFetch({
        onScenario: (body) => {
          scenarioBody = body;
          return json(
            {
              id: 'recommendation-1',
              scope: { organisation_id: 'org-1', marketplace_id: 'market-1' },
              product: {
                product_id: 'product-1',
                asin: 'B012345678',
                title: 'Travel Mug',
              },
              supplier_offer_id: 'offer-1',
              budget_amount: '12000.00',
              budget_currency_code: 'INR',
              formula_version: 'selleros.test-buy.v1',
              configuration_checksum: 'test-buy-checksum',
              inputs: { monthly_demand_units: 30, data_confidence_score: 82 },
              evidence: {
                source_snapshot_id: 'snapshot-1',
                monthly_demand_units: 30,
                monthly_demand_label: 'estimated',
                monthly_demand_source: 'keepa_monthly_sold',
                market_snapshot_at: '2026-07-18T10:00:00Z',
                market_observed_on: '2026-05-26',
                data_confidence_score_result_id: 'score-result-1',
                data_confidence_score: 82,
                data_confidence_label: 'calculated',
                data_confidence_formula_version: '1.0.0',
                supplier_offer_label: 'user_confirmed',
                budget_label: 'user_confirmed',
              },
              scenarios: [
                {
                  scenario: 'conservative',
                  quantity: 10,
                  unit_cost: '500.00',
                  required_investment: '5000.00',
                  expected_sell_through_days: '10.0',
                  status: 'recommended',
                  reason_codes: ['TEST_BUY_DEMAND_AND_LEAD_TIME_APPLIED'],
                },
                {
                  scenario: 'expected',
                  quantity: 20,
                  unit_cost: '500.00',
                  required_investment: '10000.00',
                  expected_sell_through_days: '20.0',
                  status: 'recommended',
                  reason_codes: [],
                },
                {
                  scenario: 'aggressive',
                  quantity: 25,
                  unit_cost: '475.00',
                  required_investment: '11875.00',
                  expected_sell_through_days: '25.0',
                  status: 'recommended',
                  reason_codes: [],
                },
              ],
              notices: [],
              advisory_only: true,
              outcome: 'recommended',
              decision_label: 'recommended',
              created_at: '2026-07-19T12:00:00Z',
            },
            201,
          );
        },
      }),
    );

    renderPlanning();

    expect(await screen.findByRole('heading', { name: 'Unit economics' })).toBeInTheDocument();
    expect(screen.getByText('₹1,299.00')).toBeInTheDocument();
    expect(screen.getByText('₹409.00')).toBeInTheDocument();
    expect(screen.getByText(/Seller fee worksheet/)).toBeInTheDocument();
    expect(
      screen.getByText('purchase_cost + freight_cost + prep_cost + packaging_cost'),
    ).toBeInTheDocument();
    expect(screen.getByRole('cell', { name: 'Reliable Supplies' })).toBeInTheDocument();
    expect(screen.getByText(/Price alone does not determine/)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Supplier offer'), { target: { value: 'offer-1' } });
    fireEvent.change(screen.getByLabelText('Available test budget'), {
      target: { value: '12000.00' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Generate scenarios' }));

    expect(await screen.findByRole('heading', { name: 'Conservative' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Expected' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Aggressive' })).toBeInTheDocument();
    expect(screen.getByText(/SellerOS cannot place an order/)).toBeInTheDocument();
    fireEvent.click(screen.getByText('Scenario evidence and policy version'));
    expect(screen.getByText('snapshot-1')).toBeInTheDocument();
    expect(screen.getByText('score-result-1')).toBeInTheDocument();
    expect(screen.getByText('1.0.0')).toBeInTheDocument();
    expect(scenarioBody).toEqual({
      supplier_offer_id: 'offer-1',
      budget_amount: '12000.00',
      budget_currency_code: 'INR',
    });
  });

  it('validates costs locally and sends timezone-aware effective timestamps', async () => {
    let costBody: Record<string, unknown> | undefined;
    vi.stubGlobal(
      'fetch',
      baseFetch({
        onCostProfile: (body) => {
          costBody = body;
          return json({ id: 'profile-1' }, 201);
        },
      }),
    );

    renderPlanning();
    expect(await screen.findByRole('heading', { name: 'Cost profile' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Save new profile version' }));
    expect(
      await screen.findByText(/Purchase cost must be zero or a positive decimal/),
    ).toBeVisible();
    expect(
      screen.getByText('Select whether the observed selling price includes GST.'),
    ).toBeVisible();
    expect(costBody).toBeUndefined();

    fireEvent.change(screen.getByLabelText(/^Supplier purchase cost/), {
      target: { value: '500.25' },
    });
    fireEvent.change(screen.getByLabelText('Observed selling-price tax basis'), {
      target: { value: 'tax_inclusive' },
    });
    fireEvent.change(screen.getByLabelText('Referral fee (%)'), { target: { value: '15' } });
    fireEvent.change(screen.getByLabelText('Fee source'), {
      target: { value: 'Amazon fee schedule' },
    });
    fireEvent.change(screen.getByLabelText('Fee source date (UTC)'), {
      target: { value: '2026-07-01' },
    });
    fireEvent.change(screen.getByLabelText('Fee evidence status'), {
      target: { value: 'observed' },
    });
    const effectiveFrom = screen.getByLabelText('Effective from (local time)') as HTMLInputElement;
    fireEvent.click(screen.getByRole('button', { name: 'Save new profile version' }));

    await waitFor(() => expect(costBody).toBeDefined());
    expect(costBody).toMatchObject({
      product_id: 'product-1',
      currency_code: 'INR',
      purchase_cost: '500.25',
      effective_from: new Date(effectiveFrom.value).toISOString(),
      referral_fee_rate_percent: '15',
      fulfilment_fee: null,
      fee_source: 'Amazon fee schedule',
      fee_effective_at: '2026-07-01T00:00:00Z',
      fee_status: 'observed',
      selling_price_tax_basis: 'tax_inclusive',
    });
    expect(
      await screen.findByText(
        'Cost profile saved. Economics were refreshed for the current effective version.',
      ),
    ).toBeVisible();
  });

  it('shows structured server validation errors on the supplier form', async () => {
    vi.stubGlobal(
      'fetch',
      baseFetch({
        onSupplierOffer: () =>
          json(
            {
              error: {
                code: 'supplier_offer_invalid',
                message: 'This quotation overlaps an immutable supplier record.',
                correlation_id: 'request-123',
              },
            },
            422,
          ),
      }),
    );

    renderPlanning();
    expect(
      await screen.findByRole('heading', { name: 'Record supplier offer' }),
    ).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Supplier name'), {
      target: { value: 'Reliable Supplies' },
    });
    fireEvent.change(screen.getByLabelText('Base unit cost'), { target: { value: '500' } });
    fireEvent.change(screen.getByLabelText('Minimum order quantity (units)'), {
      target: { value: '10' },
    });
    fireEvent.change(screen.getByLabelText('Lead time (days)'), {
      target: { value: '14' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save supplier offer' }));

    expect(
      await screen.findByText('This quotation overlaps an immutable supplier record.'),
    ).toBeVisible();
    expect(screen.getByText(/Support reference: request-123/)).toBeVisible();
  });

  it('keeps supplier offer 101 reachable through pagination and scenario selection', async () => {
    const pageOneItems = Array.from({ length: 100 }, (_, index) => ({
      ...offer,
      id: `offer-${index + 1}`,
      supplier: {
        id: `supplier-${index + 1}`,
        name: `Supplier ${index + 1}`,
      },
    }));
    const offer101 = {
      ...offer,
      id: 'offer-101',
      supplier: { id: 'supplier-101', name: 'Supplier 101' },
    };
    const requestedOfferUrls: string[] = [];
    vi.stubGlobal(
      'fetch',
      baseFetch({
        onOffers: (url) => {
          requestedOfferUrls.push(url);
          const page = url.includes('page=2') ? 2 : 1;
          return json({
            ...offers,
            items: page === 2 ? [offer101] : pageOneItems,
            pagination: {
              page,
              page_size: 100,
              total_items: 101,
              total_pages: 2,
              has_previous: page === 2,
              has_next: page === 1,
            },
          });
        },
      }),
    );

    renderPlanning();

    expect(await screen.findByText('101 recorded')).toBeInTheDocument();
    expect(screen.getByText(/Showing 1–100 of 101/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Next offers' }));

    expect(await screen.findByRole('cell', { name: 'Supplier 101' })).toBeInTheDocument();
    expect(screen.getByText(/Showing 101–101 of 101/)).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /Supplier 101/ })).toHaveValue('offer-101');
    expect(requestedOfferUrls.some((url) => url.includes('page=2'))).toBe(true);
  });

  it('guides first-use planning when no scoped products exist', async () => {
    window.history.replaceState({}, '', '/planning');
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        json({
          ...productList,
          items: [],
          pagination: { ...productList.pagination, total_items: 0, total_pages: 0 },
        }),
      ),
    );

    renderPlanning();

    expect(await screen.findByText('Import products before planning')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Upload Keepa workbook' })).toHaveAttribute(
      'href',
      '/imports',
    );
  });
});
