import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { DatasetOverview } from './DatasetOverview';

describe('DatasetOverview', () => {
  it('blocks revenue when monthly demand coverage is insufficient', () => {
    render(
      <DatasetOverview
        organisationId="org-1"
        marketplaceId="market-1"
        overview={{
          readiness: 'relative_research_only',
          readiness_title: 'Ready for relative product research',
          readiness_message: 'Rank and price evidence are usable.',
          product_count: 549,
          category_count: 2,
          subcategory_count: 147,
          brand_count: 227,
          monthly_demand_coverage_percentage: '0.2',
          revenue_coverage_percentage: '0.2',
          estimated_monthly_units: null,
          estimated_monthly_revenue: null,
          currency_code: null,
          price_range_currency_code: 'INR',
          coverage: [
            {
              id: 'buy_box_price',
              label: 'Current Buy Box price',
              populated_products: 549,
              total_products: 549,
              coverage_percentage: '100.0',
            },
            {
              id: 'monthly_demand',
              label: 'Bought in past month',
              populated_products: 1,
              total_products: 549,
              coverage_percentage: '0.2',
            },
          ],
          top_categories: [
            {
              label: 'Toys & Games',
              product_count: 549,
              product_percentage: '100.0',
            },
            {
              label: 'Baby',
              product_count: 10,
              product_percentage: '1.8',
            },
          ],
          top_subcategories: [
            {
              label: 'Cars & Race Cars',
              product_count: 67,
              product_percentage: '12.2',
            },
          ],
          top_brands: [
            {
              label: 'Hot Wheels',
              product_count: 71,
              product_percentage: '12.9',
            },
          ],
          price_ranges: [{ label: '500–999', product_count: 300, product_percentage: '54.6' }],
          conclusion_codes: [
            'revenue_blocked_low_monthly_demand',
            'brand_concentration_requires_review',
          ],
        }}
      />,
    );

    expect(
      screen.getByRole('heading', { name: 'Ready for relative product research' }),
    ).toBeInTheDocument();
    expect(screen.getByText('Not responsible to calculate')).toBeInTheDocument();
    expect(screen.getByLabelText('Largest categories')).toHaveTextContent('Toys & Games');
    expect(screen.getByLabelText('Brand concentration')).toHaveTextContent('Hot Wheels');
    expect(screen.getByLabelText('Selling price ranges (INR)')).toHaveTextContent('500–999');
    expect(screen.getByText(/Revenue remains hidden until at least 70%/)).toBeInTheDocument();
  });

  it('loads category charts and a ranked table when a category is selected', async () => {
    const categoryOverview = {
      readiness: 'relative_research_only' as const,
      readiness_title: 'Ready for relative product research',
      readiness_message: 'Relative evidence is usable.',
      product_count: 67,
      category_count: 1,
      subcategory_count: 2,
      brand_count: 10,
      monthly_demand_coverage_percentage: '10.0',
      revenue_coverage_percentage: '10.0',
      estimated_monthly_units: null,
      estimated_monthly_revenue: null,
      currency_code: null,
      price_range_currency_code: 'INR',
      coverage: [],
      top_categories: [{ label: 'Toys & Games', product_count: 67, product_percentage: '100.0' }],
      top_subcategories: [
        { label: 'Cars & Race Cars', product_count: 40, product_percentage: '59.7' },
      ],
      top_brands: [{ label: 'Hot Wheels', product_count: 20, product_percentage: '29.9' }],
      price_ranges: [{ label: '500–999', product_count: 40, product_percentage: '59.7' }],
      conclusion_codes: ['revenue_blocked_low_monthly_demand'],
    };
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes('/dashboard/dataset-overview')) return Response.json(categoryOverview);
        if (url.includes('/dashboard/category-cost-estimate')) {
          return Response.json({
            subcategory: 'Cars & Race Cars',
            formula_version: 'selleros.target-sourcing-cost.v1',
            configuration_checksum: 'checksum',
            assumptions: {},
            items: [],
            pagination: {
              page: 1,
              page_size: 25,
              total_items: 0,
              total_pages: 0,
              has_previous: false,
              has_next: false,
            },
          });
        }
        if (url.includes('/dashboard/research-ranking')) {
          return Response.json({
            subcategory: 'Cars & Race Cars',
            sort_by: 'research_priority',
            sort_direction: 'desc',
            formula_version: 'selleros.research-priority.v1',
            configuration_checksum: 'ranking-checksum',
            weights: {
              demand: 30,
              price_stability: 20,
              competition_quality: 15,
              data_confidence: 15,
              sales_rank_trend: 10,
              buy_box_availability: 10,
            },
            items: [
              {
                product: {
                  product_id: 'product-1',
                  asin: 'B000RANK01',
                  title: 'Ranked toy',
                  brand: 'Synthetic',
                  category: 'Toys & Games',
                  subcategory: 'Cars & Race Cars',
                  image_url: 'https://m.media-amazon.com/toy.jpg',
                  amazon_url: 'https://www.amazon.in/dp/B000RANK01',
                  latest_snapshot_id: 'snapshot-1',
                  latest_snapshot_at: '2026-05-26T00:00:00Z',
                  latest_observed_on: '2026-05-26',
                  buy_box_price: '999.00',
                  buy_box_price_90d: '950.00',
                  currency_code: 'INR',
                  offer_count: 3,
                  sales_rank: 1000,
                  sales_rank_90d: 1200,
                  estimated_monthly_bought: 200,
                  buy_box_winner_count_90d: 2,
                  buy_box_oos_percentage_90d: '5',
                  demand_score: 90,
                  competition_score: 85,
                  price_stability_score: 88,
                  overall_opportunity_score: 84,
                  data_confidence_score: 90,
                  strategy: 'test_buy',
                  recommendation_confidence: 90,
                  score_formula_version: 'selleros.market-opportunity.v1',
                  strategy_rules_version: 'strategy-v1',
                  research: null,
                  data_quality_codes: [],
                },
                ranking: {
                  rank: 1,
                  score: 88,
                  formula_version: 'selleros.research-priority.v1',
                  configuration_checksum: 'ranking-checksum',
                  warning_codes: [],
                  components: [
                    { id: 'demand', label: 'Demand', weight: 30, score: 90 },
                    {
                      id: 'price_stability',
                      label: 'Price stability',
                      weight: 20,
                      score: 88,
                    },
                    {
                      id: 'competition_quality',
                      label: 'Competition quality',
                      weight: 15,
                      score: 85,
                    },
                    {
                      id: 'data_confidence',
                      label: 'Data confidence',
                      weight: 15,
                      score: 90,
                    },
                    {
                      id: 'sales_rank_trend',
                      label: 'Sales-rank trend',
                      weight: 10,
                      score: 83,
                    },
                    {
                      id: 'buy_box_availability',
                      label: 'Buy Box availability',
                      weight: 10,
                      score: 95,
                    },
                  ],
                },
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
          });
        }
        throw new Error(`Unexpected request: ${url}`);
      }),
    );

    render(
      <DatasetOverview
        organisationId="org-1"
        marketplaceId="market-1"
        overview={{
          ...categoryOverview,
          product_count: 100,
          category_count: 2,
          top_categories: [
            { label: 'Toys & Games', product_count: 67, product_percentage: '67.0' },
            { label: 'Baby', product_count: 33, product_percentage: '33.0' },
          ],
        }}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Toys & Games' }));

    expect(
      await screen.findByRole('heading', { name: 'Toys & Games', level: 2 }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText('Toys & Games subcategories')).toHaveTextContent(
      'Cars & Race Cars',
    );
    expect(await screen.findByLabelText('Cars & Race Cars ranked products')).toBeInTheDocument();
    expect(screen.getByText('88/100')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'View on Amazon.in' })).toHaveAttribute(
      'href',
      'https://www.amazon.in/dp/B000RANK01',
    );
    expect(screen.getByRole('combobox', { name: 'Sort products by' })).toHaveValue(
      'research_priority',
    );
    expect(screen.getByRole('link', { name: 'Open full category research' })).toHaveAttribute(
      'href',
      expect.stringContaining('category=Toys%20%26%20Games'),
    );

    fireEvent.click(screen.getByRole('tab', { name: 'Target sourcing cost' }));

    expect(screen.getByLabelText('GST %')).toHaveValue(18);
    expect(screen.getByLabelText('Amazon fee %')).toHaveValue(15);
    expect(screen.getByLabelText('Target profit %')).toHaveValue(15);
    expect(screen.getByLabelText('Cars & Race Cars sourcing costs')).toBeInTheDocument();
    expect(screen.getByText(/Defaults are configurable assumptions/)).toBeInTheDocument();
  });
});
