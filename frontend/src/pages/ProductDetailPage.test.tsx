import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { Workspace } from '../api/contracts';
import { WorkspaceContext } from '../app/workspace';
import { ProductDetailPage } from './ProductDetailPage';

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

const evidence = [
  {
    reason_code: 'demand_strong',
    polarity: 'positive',
    source: 'score',
    signal: 'demand',
    observed_value: 82,
    comparison: 'gte',
    threshold_value: 70,
    threshold_upper_value: null,
    statement: 'Demand evidence is strong.',
  },
  {
    reason_code: 'competition_elevated',
    polarity: 'negative',
    source: 'score',
    signal: 'competition',
    observed_value: 48,
    comparison: 'lt',
    threshold_value: 50,
    threshold_upper_value: null,
    statement: 'Competition requires monitoring.',
  },
];

const recommendation = {
  id: 'recommendation-1',
  strategy: 'growth',
  rules_version: '1.0.0',
  configuration_checksum: 'rules-checksum',
  confidence: 88,
  evidence,
  calculated_at: '2026-07-19T10:00:00Z',
};

const snapshot = {
  id: 'snapshot-1',
  import_batch_id: 'import-1',
  snapshot_kind: 'keepa_import',
  snapshot_at: '2026-07-19T10:00:00Z',
  metrics: {
    buy_box_price: '1299.00',
    buy_box_price_90d: '1320.00',
    currency_code: 'INR',
    sales_rank: 1200,
    sales_rank_90d: 1500,
    sales_rank_drops_90d: 32,
    review_rating: '4.5',
    review_count: 240,
    new_offer_count: 4,
    total_offer_count: 5,
    buy_box_winner_count_90d: 2,
    buy_box_oos_percentage_90d: '1.2',
    monthly_sold: null,
    is_fba: true,
  },
  scores: [
    {
      id: 'score-1',
      name: 'demand',
      value: 82,
      formula_version: '1.0.0',
      configuration_checksum: 'score-checksum',
      inputs: { sales_rank: 1200 },
      reason_codes: ['rank_strong'],
      calculated_at: '2026-07-19T10:00:00Z',
    },
    {
      id: 'score-2',
      name: 'data_confidence',
      value: 90,
      formula_version: '1.0.0',
      configuration_checksum: 'score-checksum',
      inputs: {},
      reason_codes: [],
      calculated_at: '2026-07-19T10:00:00Z',
    },
  ],
  recommendation,
};

describe('ProductDetailPage', () => {
  beforeEach(() => window.history.replaceState({}, '', '/products/product-1'));

  it('renders scores, strategy evidence, missing-data notices and snapshot history', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        Response.json({
          scope: { organisation_id: 'org-1', marketplace_id: 'market-1' },
          product: {
            product_id: 'product-1',
            asin: 'B012345678',
            title: 'Travel Mug',
            brand: 'Acme',
            category: 'Kitchen',
            subcategory: 'Drinkware',
            image_url: null,
            amazon_url: 'https://www.amazon.in/dp/B012345678',
            created_at: '2026-07-19T09:00:00Z',
          },
          latest_snapshot: snapshot,
          notices: [
            {
              code: 'monthly_sold_missing',
              severity: 'missing',
              field: 'monthly_sold',
              message: 'The monthly-sold estimate is missing.',
            },
          ],
          snapshot_history: [snapshot],
          strategy_history: [
            {
              snapshot_id: 'snapshot-1',
              snapshot_at: '2026-07-19T10:00:00Z',
              strategy: 'growth',
              confidence: 88,
              rules_version: '1.0.0',
              evidence,
            },
          ],
        }),
      ),
    );
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
        <ProductDetailPage productId="product-1" />
      </WorkspaceContext.Provider>,
    );

    expect(await screen.findByRole('heading', { name: 'Travel Mug' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Growth' })).toBeInTheDocument();
    expect(screen.getByText('Demand evidence is strong.')).toBeInTheDocument();
    expect(screen.getByText('Competition requires monitoring.')).toBeInTheDocument();
    expect(screen.getByText('The monthly-sold estimate is missing.')).toBeInTheDocument();
    expect(screen.getByText('Demand Score')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'View Amazon listing' })).toHaveAttribute(
      'href',
      'https://www.amazon.in/dp/B012345678',
    );
    expect(screen.getByRole('table')).toBeInTheDocument();
  });

  it('withholds strategy labels when the API has no supported recommendation', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        Response.json({
          scope: { organisation_id: 'org-1', marketplace_id: 'market-1' },
          product: {
            product_id: 'product-2',
            asin: 'B087654321',
            title: 'Evidence Pending Product',
            brand: null,
            category: null,
            subcategory: null,
            image_url: null,
            amazon_url: null,
            created_at: '2026-07-19T09:00:00Z',
          },
          latest_snapshot: {
            ...snapshot,
            id: 'snapshot-2',
            recommendation: null,
            scores: [],
          },
          notices: [
            {
              code: 'recommendation_missing',
              severity: 'missing',
              field: 'recommendation',
              message: 'A supported recommendation is not available.',
            },
          ],
          snapshot_history: [],
          strategy_history: [],
        }),
      ),
    );
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
        <ProductDetailPage productId="product-2" />
      </WorkspaceContext.Provider>,
    );

    expect(
      await screen.findByRole('heading', { name: 'No supported recommendation' }),
    ).toBeInTheDocument();
    expect(screen.queryByText('Recommended · advisory only')).not.toBeInTheDocument();
    expect(screen.queryByText('Discovery')).not.toBeInTheDocument();
  });
});
