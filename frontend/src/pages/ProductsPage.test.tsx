import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { Workspace } from '../api/contracts';
import { WorkspaceContext } from '../app/workspace';
import { ProductsPage } from './ProductsPage';

const workspace: Workspace = {
  organisation_id: 'org-1',
  organisation_name: 'Acme',
  marketplaces: [
    {
      id: 'market-1',
      code: 'IN',
      name: 'Amazon India',
      default_currency_code: 'INR',
    },
  ],
};

function response() {
  return Response.json({
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
        latest_snapshot_at: '2026-07-01T10:00:00Z',
        buy_box_price: '1299.00',
        currency_code: 'INR',
        offer_count: 4,
        overall_opportunity_score: 82,
        data_confidence_score: 91,
        strategy: 'growth',
        recommendation_confidence: 88,
        score_formula_version: '1.0.0',
        strategy_rules_version: '1.0.0',
        data_quality_codes: [],
      },
    ],
    pagination: {
      page: 2,
      page_size: 25,
      total_items: 26,
      total_pages: 2,
      has_previous: true,
      has_next: false,
    },
    query: {},
  });
}

describe('ProductsPage', () => {
  beforeEach(() => {
    window.history.replaceState({}, '', '/products?strategy=growth&page=2&columns=overall%2Cprice');
    vi.stubGlobal('scrollTo', vi.fn());
  });

  it('hydrates filters from the URL and resets pagination when filters change', async () => {
    const fetchMock = vi.fn<(input: RequestInfo | URL, options?: RequestInit) => Promise<Response>>(
      async () => response(),
    );
    vi.stubGlobal('fetch', fetchMock);
    const marketplace = workspace.marketplaces[0];
    if (!marketplace) throw new Error('Fixture requires a marketplace');

    render(
      <WorkspaceContext.Provider
        value={{
          workspaces: [workspace],
          selection: { workspace, marketplace },
          select: vi.fn(),
          addWorkspace: vi.fn(),
        }}
      >
        <ProductsPage />
      </WorkspaceContext.Provider>,
    );

    expect(await screen.findByText('Travel Mug')).toBeInTheDocument();
    expect(screen.getByLabelText('Strategy')).toHaveValue('growth');
    expect(fetchMock.mock.calls[0]?.[0]).toContain('strategy=growth');
    expect(fetchMock.mock.calls[0]?.[0]).toContain('page=2');
    expect(fetchMock.mock.calls[0]?.[0]).not.toContain('columns=');
    expect(screen.getByRole('columnheader', { name: 'Overall' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Observed price' })).toBeInTheDocument();
    expect(screen.queryByRole('columnheader', { name: 'Recommendation' })).not.toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: 'Overall score' })).toBeChecked();
    expect(screen.getByRole('checkbox', { name: 'Recommendation' })).not.toBeChecked();

    fireEvent.change(screen.getByLabelText('Search products'), { target: { value: 'mug' } });
    fireEvent.submit(screen.getByLabelText('Search products').closest('form') as HTMLFormElement);

    await waitFor(() => expect(window.location.search).toContain('search=mug'));
    expect(window.location.search).toContain('page=1');
    expect(window.location.search).toContain('strategy=growth');
    expect(window.location.search).toContain('columns=overall%2Cprice');
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  });
});
