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
        if (url.includes('/products?')) {
          return Response.json({
            scope: { organisation_id: 'org-1', marketplace_id: 'market-1' },
            items: [],
            pagination: {
              page: 1,
              page_size: 10,
              total_items: 0,
              total_pages: 0,
              has_previous: false,
              has_next: false,
            },
            query: {},
            research_policy_version: 'product-research-v1.0.0',
            research_configuration_checksum: 'checksum',
            screens: [],
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
    expect(await screen.findByLabelText('Cars & Race Cars Keepa products')).toBeInTheDocument();
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
