import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import type { CostProfile, CreateCostProfileRequest } from '../../api/contracts';
import { CostProfileForm } from './CostProfileForm';
import { CostProfileHistory } from './CostProfileHistory';

const productProfile: CostProfile = {
  id: 'profile-product-1',
  organisation_id: 'org-1',
  marketplace_id: 'market-1',
  product_id: 'product-1',
  scope: 'product',
  version: 2,
  supersedes_profile_id: 'profile-product-0',
  currency_code: 'INR',
  purchase_cost: '500.2500',
  gst_rate_percent: '18.0000',
  gst_recoverable_percent: '100.0000',
  freight_cost: '25.0000',
  prep_cost: '5.0000',
  packaging_cost: '10.0000',
  advertising_rate_percent: '8.0000',
  returns_rate_percent: '3.0000',
  overhead_cost: '4.0000',
  referral_fee_rate_percent: '15.0000',
  fulfilment_fee: '70.0000',
  closing_fee: '10.0000',
  storage_fee: '2.0000',
  fee_source: 'Amazon fee schedule',
  fee_effective_at: '2026-07-01T00:00:00Z',
  fee_status: 'observed',
  minimum_margin_percent: '12.0000',
  target_margin_percent: '20.0000',
  configuration_checksum: 'product-checksum',
  effective_from: '2026-07-10T00:00:00Z',
  effective_to: null,
  created_at: '2026-07-10T08:00:00Z',
  evidence_label: 'user_confirmed',
  selling_price_tax_basis: 'tax_inclusive',
};

const marketplaceProfile: CostProfile = {
  ...productProfile,
  id: 'profile-default-1',
  product_id: null,
  scope: 'marketplace_default',
  version: 3,
  purchase_cost: '300.0000',
  referral_fee_rate_percent: '12.0000',
  fee_source: 'Marketplace default schedule',
  configuration_checksum: 'default-checksum',
  selling_price_tax_basis: 'tax_exclusive',
};

function input(name: string): HTMLInputElement {
  return screen.getByLabelText(name) as HTMLInputElement;
}

describe('CostProfileForm scope isolation', () => {
  it('clears product financial and fee values when switching to marketplace default', () => {
    render(
      <CostProfileForm
        productId="product-1"
        currencyCode="INR"
        profilesByScope={{ product: productProfile, marketplace_default: null }}
        history={[productProfile]}
        onCreate={vi.fn(async () => undefined)}
      />,
    );

    expect(input('Supplier purchase cost (GST-exclusive)')).toHaveValue(500.25);
    expect(input('Referral fee (%)')).toHaveValue(15);
    expect(input('Fee source')).toHaveValue('Amazon fee schedule');
    expect(
      screen.getByText(/Prefilled from the latest active product revision/),
    ).toBeInTheDocument();

    fireEvent.change(input('Supplier purchase cost (GST-exclusive)'), {
      target: { value: '777.00' },
    });
    fireEvent.click(screen.getByLabelText('Marketplace default'));

    expect(input('Supplier purchase cost (GST-exclusive)')).toHaveValue(null);
    expect(input('Referral fee (%)')).toHaveValue(null);
    expect(input('Fee source')).toHaveValue('');
    expect(screen.getByLabelText('Fee evidence status')).toHaveValue('');
    expect(screen.getByText('No matching scoped revision · inputs reset')).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText('This product'));

    expect(input('Supplier purchase cost (GST-exclusive)')).toHaveValue(500.25);
    expect(input('Referral fee (%)')).toHaveValue(15);
    expect(input('Fee source')).toHaveValue('Amazon fee schedule');
  });

  it('does not prefill a marketplace default into the initial product target', () => {
    render(
      <CostProfileForm
        productId="product-1"
        currencyCode="INR"
        profilesByScope={{ product: null, marketplace_default: marketplaceProfile }}
        history={[marketplaceProfile]}
        onCreate={vi.fn(async () => undefined)}
      />,
    );

    expect(screen.getByLabelText('This product')).toBeChecked();
    expect(input('Supplier purchase cost (GST-exclusive)')).toHaveValue(null);
    expect(input('Referral fee (%)')).toHaveValue(null);
    expect(input('Fee source')).toHaveValue('');

    fireEvent.click(screen.getByLabelText('Marketplace default'));

    expect(input('Supplier purchase cost (GST-exclusive)')).toHaveValue(300);
    expect(input('Referral fee (%)')).toHaveValue(12);
    expect(input('Fee source')).toHaveValue('Marketplace default schedule');
    expect(
      screen.getByText(/Prefilled from the latest active marketplace-default revision/),
    ).toBeInTheDocument();
  });

  it('prefills each scope only from its own profile when both exist', () => {
    render(
      <CostProfileForm
        productId="product-1"
        currencyCode="INR"
        profilesByScope={{
          product: productProfile,
          marketplace_default: marketplaceProfile,
        }}
        history={[productProfile, marketplaceProfile]}
        onCreate={vi.fn(async () => undefined)}
      />,
    );

    expect(input('Supplier purchase cost (GST-exclusive)')).toHaveValue(500.25);
    expect(screen.getByLabelText('Observed selling-price tax basis')).toHaveValue('tax_inclusive');

    fireEvent.click(screen.getByLabelText('Marketplace default'));

    expect(input('Supplier purchase cost (GST-exclusive)')).toHaveValue(300);
    expect(input('Fee source')).toHaveValue('Marketplace default schedule');
    expect(screen.getByLabelText('Observed selling-price tax basis')).toHaveValue('tax_exclusive');
  });

  it('preserves the marketplace-default target when that scope refreshes', () => {
    const view = render(
      <CostProfileForm
        productId="product-1"
        currencyCode="INR"
        profilesByScope={{
          product: productProfile,
          marketplace_default: marketplaceProfile,
        }}
        history={[productProfile, marketplaceProfile]}
        onCreate={vi.fn(async () => undefined)}
      />,
    );
    fireEvent.click(screen.getByLabelText('Marketplace default'));
    expect(screen.getByLabelText('Marketplace default')).toBeChecked();

    view.rerender(
      <CostProfileForm
        productId="product-1"
        currencyCode="INR"
        profilesByScope={{
          product: productProfile,
          marketplace_default: {
            ...marketplaceProfile,
            id: 'profile-default-2',
            purchase_cost: '310.0000',
          },
        }}
        history={[
          productProfile,
          { ...marketplaceProfile, id: 'profile-default-2', purchase_cost: '310.0000' },
        ]}
        onCreate={vi.fn(async () => undefined)}
      />,
    );

    expect(screen.getByLabelText('Marketplace default')).toBeChecked();
    expect(input('Supplier purchase cost (GST-exclusive)')).toHaveValue(310);
  });

  it('creates a timezone-explicit revision later on the same day', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-07-19T12:00:00Z'));
    try {
      const onCreate = vi.fn<(command: CreateCostProfileRequest) => Promise<void>>();
      onCreate.mockResolvedValue(undefined);
      const sameDayProfile = {
        ...productProfile,
        effective_from: '2026-07-19T08:00:00Z',
      };
      render(
        <CostProfileForm
          productId="product-1"
          currencyCode="INR"
          profilesByScope={{ product: sameDayProfile, marketplace_default: null }}
          history={[sameDayProfile]}
          onCreate={onCreate}
        />,
      );

      expect(
        screen.getByText(/All fixed cost amounts in this section are per sellable unit/),
      ).toBeInTheDocument();
      expect(
        screen.getByText(/Fulfilment, closing and storage fees are per sellable unit/),
      ).toBeInTheDocument();
      fireEvent.click(screen.getByRole('button', { name: 'Save new profile version' }));

      expect(onCreate).toHaveBeenCalledTimes(1);
      const command = onCreate.mock.calls[0]?.[0];
      expect(command?.effective_from).toBe('2026-07-19T12:00:00.000Z');
      expect(Date.parse(command?.effective_from ?? '')).toBeGreaterThan(
        Date.parse(sameDayProfile.effective_from),
      );
      expect(command?.effective_from.slice(0, 10)).toBe(sameDayProfile.effective_from.slice(0, 10));
    } finally {
      vi.useRealTimers();
    }
  });

  it('uses the latest scheduled revision as the next revision baseline', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-07-19T12:00:00Z'));
    try {
      const activeProfile = {
        ...productProfile,
        effective_from: '2026-07-19T08:00:00Z',
        effective_to: '2026-07-20T08:00:00Z',
      };
      const scheduledProfile = {
        ...productProfile,
        id: 'profile-product-3',
        version: 3,
        supersedes_profile_id: activeProfile.id,
        purchase_cost: '501.0049',
        effective_from: '2026-07-20T08:00:00Z',
        effective_to: null,
      };
      const onCreate = vi.fn<(command: CreateCostProfileRequest) => Promise<void>>();
      onCreate.mockResolvedValue(undefined);
      render(
        <CostProfileForm
          productId="product-1"
          currencyCode="INR"
          profilesByScope={{ product: activeProfile, marketplace_default: null }}
          history={[scheduledProfile, activeProfile]}
          onCreate={onCreate}
        />,
      );

      expect(input('Supplier purchase cost (GST-exclusive)')).toHaveValue(501.0049);
      expect(
        screen.getByText(/Prefilled from the latest scheduled product revision/),
      ).toBeInTheDocument();
      fireEvent.click(screen.getByRole('button', { name: 'Save new profile version' }));

      const command = onCreate.mock.calls[0]?.[0];
      expect(Date.parse(command?.effective_from ?? '')).toBeGreaterThan(
        Date.parse(scheduledProfile.effective_from),
      );
    } finally {
      vi.useRealTimers();
    }
  });
});

describe('CostProfileHistory precedence', () => {
  it('identifies the product profile selected over the marketplace default', () => {
    render(
      <CostProfileHistory
        profileSource="product"
        activeProfile={productProfile}
        history={[productProfile, marketplaceProfile]}
      />,
    );

    expect(screen.getByText('Applied profile')).toBeInTheDocument();
    expect(screen.getByText('Product')).toBeInTheDocument();
    expect(screen.getByText('Price includes GST')).toBeInTheDocument();
  });

  it('labels scheduled, active and ended revisions by their effective windows', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-07-19T12:00:00Z'));
    try {
      const activeProfile = {
        ...productProfile,
        effective_to: '2026-07-20T08:00:00Z',
        purchase_cost: '1.0049',
      };
      const scheduledProfile = {
        ...productProfile,
        id: 'profile-product-3',
        version: 3,
        effective_from: '2026-07-20T08:00:00Z',
        effective_to: null,
        purchase_cost: '1.0001',
      };
      const endedProfile = {
        ...productProfile,
        id: 'profile-product-1',
        version: 1,
        effective_from: '2026-07-01T08:00:00Z',
        effective_to: '2026-07-10T08:00:00Z',
      };
      render(
        <CostProfileHistory
          profileSource="product"
          activeProfile={activeProfile}
          history={[scheduledProfile, activeProfile, endedProfile]}
        />,
      );
      fireEvent.click(screen.getByText('Review effective-dated versions'));

      expect(screen.getByRole('row', { name: /3 Product specific.*Scheduled/ })).toHaveTextContent(
        '1.0001',
      );
      expect(screen.getByRole('row', { name: /2 Product specific.*Active/ })).toHaveTextContent(
        '1.0049',
      );
      expect(screen.getByRole('row', { name: /1 Product specific.*Ended/ })).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });
});
