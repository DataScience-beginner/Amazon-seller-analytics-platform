import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import type { SupplierOffer, TestBuyRecommendation } from '../../api/contracts';
import { TestBuyPlanner } from './TestBuyPlanner';

const offer: SupplierOffer = {
  id: 'offer-1',
  product_id: 'product-1',
  supplier: { id: 'supplier-1', name: 'Reliable Supplies' },
  currency_code: 'INR',
  minimum_order_quantity: 10,
  unit_cost: '500.00',
  lead_time_days: 14,
  quotation_date: '2026-07-01',
  valid_until: null,
  notes: null,
  price_tiers: [],
  created_at: '2026-07-01T08:00:00Z',
  evidence_label: 'user_confirmed',
};

const blockedRecommendation: TestBuyRecommendation = {
  id: 'recommendation-1',
  scope: { organisation_id: 'org-1', marketplace_id: 'market-1' },
  product: { product_id: 'product-1', asin: 'B012345678', title: 'Travel Mug' },
  supplier_offer_id: 'offer-1',
  budget_amount: '12000.00',
  budget_currency_code: 'INR',
  formula_version: 'selleros.test-buy.v1',
  configuration_checksum: 'test-buy-checksum',
  inputs: { monthly_demand_units: null, data_confidence_score: null },
  evidence: {
    source_snapshot_id: 'snapshot-1',
    monthly_demand_units: null,
    monthly_demand_label: null,
    monthly_demand_source: null,
    market_snapshot_at: '2026-07-18T10:00:00Z',
    data_confidence_score_result_id: null,
    data_confidence_score: null,
    data_confidence_label: null,
    data_confidence_formula_version: null,
    supplier_offer_label: 'user_confirmed',
    budget_label: 'user_confirmed',
  },
  scenarios: (['conservative', 'expected', 'aggressive'] as const).map((scenario) => ({
    scenario,
    quantity: 0,
    unit_cost: null,
    required_investment: '0.00',
    expected_sell_through_days: null,
    status: 'blocked',
    reason_codes: ['TEST_BUY_MONTHLY_DEMAND_REQUIRED'],
  })),
  notices: [
    {
      code: 'TEST_BUY_MONTHLY_DEMAND_REQUIRED',
      severity: 'missing',
      message: 'Monthly demand evidence is required before a quantity can be recommended.',
      evidence_label: 'recommended',
    },
  ],
  advisory_only: true,
  outcome: 'blocked',
  decision_label: null,
  created_at: '2026-07-19T12:00:00Z',
};

describe('TestBuyPlanner evidence semantics', () => {
  it('uses neutral wording before generation and labels an all-blocked response as Blocked', async () => {
    const onGenerate = vi.fn(async () => blockedRecommendation);
    render(<TestBuyPlanner offers={[offer]} currencyCode="INR" onGenerate={onGenerate} />);

    expect(screen.getByText('Advisory planning')).toBeInTheDocument();
    expect(screen.queryByText('Recommended · advisory only')).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Supplier offer'), {
      target: { value: 'offer-1' },
    });
    fireEvent.change(screen.getByLabelText('Available test budget'), {
      target: { value: '12000.00' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Generate scenarios' }));

    expect(
      await screen.findByRole('heading', { name: 'Test-buy scenarios · Blocked' }),
    ).toBeInTheDocument();
    expect(screen.getByText('Blocked · advisory only')).toBeInTheDocument();
    expect(screen.queryByText(/Estimated from Keepa monthly sold/)).not.toBeInTheDocument();
    expect(screen.getByText('Missing · no demand estimate is available')).toBeInTheDocument();
    expect(screen.getByText('Missing · no calculated confidence is available')).toBeInTheDocument();
    expect(screen.queryByText('Recommended · advisory only')).not.toBeInTheDocument();
  });

  it('excludes offers in another currency because FX is not inferred', () => {
    render(
      <TestBuyPlanner
        offers={[{ ...offer, currency_code: 'USD' }]}
        currencyCode="INR"
        onGenerate={vi.fn(async () => blockedRecommendation)}
      />,
    );

    expect(screen.getByText(/SellerOS does not infer or convert FX rates/)).toBeInTheDocument();
    expect(
      screen.getByText('A marketplace-currency supplier offer is required'),
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Generate scenarios' })).not.toBeInTheDocument();
  });
});
