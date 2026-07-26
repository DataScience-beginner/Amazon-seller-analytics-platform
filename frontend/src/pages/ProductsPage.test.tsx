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
        buy_box_price_90d: '1250.00',
        currency_code: 'INR',
        offer_count: 4,
        sales_rank: 2400,
        sales_rank_90d: 2600,
        estimated_monthly_bought: 500,
        buy_box_winner_count_90d: 2,
        buy_box_oos_percentage_90d: '4.5',
        demand_score: 88,
        competition_score: 84,
        price_stability_score: 86,
        overall_opportunity_score: 82,
        data_confidence_score: 91,
        strategy: 'growth',
        recommendation_confidence: 88,
        score_formula_version: '1.0.0',
        strategy_rules_version: '1.0.0',
        research: {
          status: 'priority_research',
          brand_classification: 'declared_brand',
          policy_version: 'product-research-v1.0.0',
          configuration_checksum: 'abc123',
          reason_codes: ['priority_thresholds_met'],
          positive_signals: ['Strong demand evidence'],
          risk_signals: ['Brand authorisation is not verified'],
          missing_evidence: ['Supplier cost'],
        },
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
    research_policy_version: 'product-research-v1.0.0',
    research_configuration_checksum: 'abc123',
    screens: [
      {
        id: 'priority_research',
        label: 'Priority research',
        description: 'Strongest candidates for further checks.',
      },
      {
        id: 'promising',
        label: 'Promising',
        description: 'Broader candidates for investigation.',
      },
    ],
  });
}

describe('ProductsPage', () => {
  beforeEach(() => {
    window.history.replaceState(
      {},
      '',
      '/products?screen=promising&page=2&brand_classification=declared_brand',
    );
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
    expect(screen.getByLabelText('Brand evidence')).toHaveValue('declared_brand');
    expect(fetchMock.mock.calls[0]?.[0]).toContain('screen=promising');
    expect(fetchMock.mock.calls[0]?.[0]).toContain('brand_classification=declared_brand');
    expect(fetchMock.mock.calls[0]?.[0]).toContain('page=2');
    expect(screen.getByRole('columnheader', { name: 'Research action' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Est. bought/month' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Seller offers' })).toBeInTheDocument();
    expect(screen.getAllByText('Priority Research')).not.toHaveLength(0);
    expect(screen.getAllByText('Declared brand')).not.toHaveLength(0);
    expect(screen.getByText(/shortlist for research only/i)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Search ASIN, title or brand'), {
      target: { value: 'mug' },
    });
    fireEvent.submit(
      screen.getByLabelText('Search ASIN, title or brand').closest('form') as HTMLFormElement,
    );

    await waitFor(() => expect(window.location.search).toContain('search=mug'));
    expect(window.location.search).toContain('page=1');
    expect(window.location.search).toContain('screen=promising');
    expect(window.location.search).toContain('brand_classification=declared_brand');
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  });
});
