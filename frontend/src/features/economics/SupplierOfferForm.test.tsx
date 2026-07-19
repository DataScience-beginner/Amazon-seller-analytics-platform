import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import type { CreateSupplierOfferRequest, SupplierOffer } from '../../api/contracts';
import { SupplierOfferForm } from './SupplierOfferForm';

const savedOffer: SupplierOffer = {
  id: 'offer-1',
  product_id: 'product-1',
  supplier: { id: 'supplier-1', name: 'Reliable Supplies' },
  currency_code: 'INR',
  minimum_order_quantity: 10,
  unit_cost: '100.0000',
  lead_time_days: 14,
  quotation_date: '2026-07-19',
  valid_until: null,
  notes: null,
  price_tiers: [
    { minimum_quantity: 10, unit_cost: '100.0000' },
    { minimum_quantity: 30, unit_cost: '80.0000' },
  ],
  created_at: '2026-07-19T12:00:00Z',
  evidence_label: 'user_confirmed',
};

describe('SupplierOfferForm tiers', () => {
  it('keeps stable controlled tier rows and submits exactly the remaining tiers', async () => {
    let command: CreateSupplierOfferRequest | undefined;
    render(
      <SupplierOfferForm
        productId="product-1"
        currencyCode="INR"
        onCreate={async (submitted) => {
          command = submitted;
          return savedOffer;
        }}
      />,
    );

    fireEvent.change(screen.getByLabelText('Supplier name'), {
      target: { value: 'Reliable Supplies' },
    });
    fireEvent.change(screen.getByLabelText('Base unit cost'), { target: { value: '100.0000' } });
    fireEvent.change(screen.getByLabelText('Minimum order quantity (units)'), {
      target: { value: '10' },
    });
    fireEvent.change(screen.getByLabelText('Lead time (days)'), { target: { value: '14' } });

    fireEvent.click(screen.getByRole('button', { name: 'Add price tier' }));
    fireEvent.click(screen.getByRole('button', { name: 'Add price tier' }));

    let quantities = screen.getAllByLabelText('Minimum units');
    let costs = screen.getAllByLabelText('Unit cost');
    fireEvent.change(quantities[0] as HTMLInputElement, { target: { value: '20' } });
    fireEvent.change(costs[0] as HTMLInputElement, { target: { value: '90.0000' } });
    fireEvent.change(quantities[1] as HTMLInputElement, { target: { value: '30' } });
    fireEvent.change(costs[1] as HTMLInputElement, { target: { value: '80.0000' } });

    fireEvent.click(screen.getByRole('button', { name: 'Remove tier 1' }));

    quantities = screen.getAllByLabelText('Minimum units');
    costs = screen.getAllByLabelText('Unit cost');
    expect(quantities).toHaveLength(1);
    expect(quantities[0]).toHaveValue(30);
    expect(costs[0]).toHaveValue(80);

    fireEvent.change(screen.getByLabelText('Marketplace currency'), {
      target: { value: 'USD' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save supplier offer' }));

    await waitFor(() => expect(command).toBeDefined());
    expect(command).toMatchObject({
      product_id: 'product-1',
      currency_code: 'INR',
      minimum_order_quantity: 10,
      unit_cost: '100.0000',
      price_tiers: [{ minimum_quantity: 30, unit_cost: '80.0000' }],
    });
  });

  it('defaults quotation date to the UTC calendar and explains the timezone contract', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-05-25T20:00:00Z'));
    try {
      render(
        <SupplierOfferForm
          productId="product-1"
          currencyCode="INR"
          onCreate={async () => savedOffer}
        />,
      );

      expect(screen.getByLabelText('Quotation date (UTC)')).toHaveValue('2026-05-25');
      expect(screen.getByLabelText('Valid until (UTC, optional)')).toBeInTheDocument();
      expect(
        screen.getByText(/Uses the UTC calendar to match server validation/),
      ).toBeInTheDocument();
      expect(screen.getByText(/future phase/)).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });
});
