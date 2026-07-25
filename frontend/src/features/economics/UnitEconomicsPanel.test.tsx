import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { ProductEconomicsResponse } from '../../api/contracts';
import { formatUtcDate } from '../../utils/format';
import { UnitEconomicsPanel } from './UnitEconomicsPanel';

const economics: ProductEconomicsResponse = {
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
  profile_source: 'product',
  active_profile: null,
  profiles_by_scope: { product: null, marketplace_default: null },
  profile_history: [],
  calculation: {
    formula_version: 'selleros.unit-economics.v1',
    configuration_checksum: 'economics-checksum',
    status: 'partial',
    decision_label: 'calculated',
    selling_price_tax_basis: null,
    inputs: { selling_price: '1299.00', purchase_cost: '500.00' },
    formulas: { landed_cost: 'purchase_cost + per_unit_costs' },
    outputs: {
      landed_cost: '500.00',
      net_revenue: null,
      output_gst: null,
      amazon_fees: null,
      contribution_profit: null,
      margin_percent: null,
      roi_percent: null,
      break_even_price: null,
      minimum_acceptable_price: null,
      target_price: null,
    },
    reason_codes: ['ECONOMICS_SELLING_PRICE_TAX_BASIS_REQUIRED'],
    fee_evidence: { status: null, source: null, effective_at: null },
  },
  notices: [],
  audit_history: [],
};

describe('UnitEconomicsPanel tax evidence', () => {
  it('shows unknown tax basis and blocked price-dependent outputs honestly', () => {
    render(<UnitEconomicsPanel economics={economics} />);

    expect(screen.getByText('Selling-price tax basis is unknown.')).toBeInTheDocument();
    const netRevenue = screen.getByRole('heading', { name: 'Net revenue' }).closest('article');
    const outputGst = screen
      .getByRole('heading', { name: 'Output GST within selling price' })
      .closest('article');
    expect(netRevenue).toHaveTextContent('Unavailable');
    expect(netRevenue).not.toHaveTextContent('Calculated');
    expect(outputGst).toHaveTextContent('Unavailable');
    expect(outputGst).not.toHaveTextContent('Calculated');
    expect(screen.getByText(/Observed on May 26, 2026/)).toHaveTextContent(
      'processed Jul 18, 2026',
    );
  });

  it('does not use the processing timestamp when the market observation date is unconfirmed', () => {
    render(
      <UnitEconomicsPanel
        economics={{
          ...economics,
          observed_price: economics.observed_price
            ? { ...economics.observed_price, observed_on: null }
            : null,
          notices: [
            {
              code: 'MARKET_OBSERVATION_DATE_UNCONFIRMED',
              severity: 'warning',
              message: 'The imported market evidence has no user-confirmed observation date.',
              evidence_label: 'observed',
            },
          ],
        }}
      />,
    );

    expect(screen.getByText(/Observation date unavailable/)).toHaveTextContent(
      'processed Jul 18, 2026',
    );
    expect(
      screen.getByText('The imported market evidence has no user-confirmed observation date.'),
    ).toBeInTheDocument();
  });

  it('labels fee source dates explicitly in UTC', () => {
    const calculation = economics.calculation;
    if (!calculation) throw new Error('Fixture requires a calculation');
    const feeEffectiveAt = '2026-01-01T00:00:00Z';
    render(
      <UnitEconomicsPanel
        economics={{
          ...economics,
          calculation: {
            ...calculation,
            fee_evidence: {
              status: 'observed',
              source: 'Amazon fee schedule',
              effective_at: feeEffectiveAt,
            },
          },
        }}
      />,
    );

    expect(screen.getByText('Amazon fee evidence').parentElement).toHaveTextContent(
      `${formatUtcDate(feeEffectiveAt)} UTC`,
    );
  });
});
