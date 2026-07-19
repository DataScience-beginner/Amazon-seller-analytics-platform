import { describe, expect, it } from 'vitest';

import type { CreateCostProfileRequest, CreateSupplierOfferRequest } from '../../api/contracts';
import { validateCostProfile, validateSupplierOffer, validateTestBuy } from './validation';

const validProfile: CreateCostProfileRequest = {
  product_id: 'product-1',
  currency_code: 'INR',
  purchase_cost: '100.00',
  gst_rate_percent: '18',
  gst_recoverable_percent: '100',
  freight_cost: '5',
  prep_cost: '2',
  packaging_cost: '3',
  advertising_rate_percent: '5',
  returns_rate_percent: '2',
  overhead_cost: '1',
  referral_fee_rate_percent: null,
  fulfilment_fee: null,
  closing_fee: null,
  storage_fee: null,
  fee_source: null,
  fee_effective_at: null,
  fee_status: null,
  minimum_margin_percent: '10',
  target_margin_percent: '20',
  selling_price_tax_basis: 'tax_inclusive',
  effective_from: '2026-07-19T00:00:00Z',
};

const validOffer: CreateSupplierOfferRequest = {
  product_id: 'product-1',
  supplier_name: 'Reliable Supplies',
  currency_code: 'INR',
  minimum_order_quantity: 10,
  unit_cost: '100',
  lead_time_days: 7,
  quotation_date: '2026-07-19',
  valid_until: null,
  notes: null,
  price_tiers: [],
};

describe('economics form validation', () => {
  it('requires margins below 100 and target margin at or above minimum', () => {
    expect(
      validateCostProfile({
        ...validProfile,
        minimum_margin_percent: '100',
        target_margin_percent: '99',
      }),
    ).toMatchObject({ minimum_margin_percent: 'Minimum margin must be less than 100%.' });

    expect(
      validateCostProfile({
        ...validProfile,
        minimum_margin_percent: '25',
        target_margin_percent: '24.99',
      }),
    ).toMatchObject({ target_margin_percent: 'Target margin cannot be below minimum margin.' });
  });

  it('keeps fee evidence complete and rejects metadata without fee inputs', () => {
    expect(
      validateCostProfile({
        ...validProfile,
        referral_fee_rate_percent: '15',
      }),
    ).toMatchObject({
      fee_source: 'Fee source is required for fee inputs.',
      fee_effective_at: 'Fee source date is required for fee inputs.',
      fee_status: 'Select how the fee inputs were established.',
    });

    expect(
      validateCostProfile({
        ...validProfile,
        fee_source: 'Amazon schedule',
      }),
    ).toMatchObject({
      fee_source: 'Clear fee evidence metadata when no fee inputs are provided.',
    });
  });

  it('requires additional discount tiers to start above MOQ and increase', () => {
    expect(
      validateSupplierOffer({
        ...validOffer,
        price_tiers: [
          { minimum_quantity: 10, unit_cost: '95' },
          { minimum_quantity: 10, unit_cost: '90' },
        ],
      }),
    ).toMatchObject({
      'price_tiers.0.minimum_quantity': 'Discount tier quantity must be greater than the base MOQ.',
      'price_tiers.1.minimum_quantity': 'Tier quantities must increase without duplicates.',
    });
  });

  it('accepts a zero advisory budget and limits currency precision to two decimals', () => {
    expect(
      validateTestBuy({
        supplier_offer_id: 'offer-1',
        budget_amount: '0',
        budget_currency_code: 'INR',
      }),
    ).toEqual({});
    expect(
      validateTestBuy({
        supplier_offer_id: 'offer-1',
        budget_amount: '10.001',
        budget_currency_code: 'INR',
      }),
    ).toMatchObject({
      budget_amount: 'Budget must be zero or a positive decimal with up to 2 decimal places.',
    });
  });
});
