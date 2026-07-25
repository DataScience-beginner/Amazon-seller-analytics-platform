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
          category_count: 1,
          subcategory_count: 147,
          brand_count: 227,
          monthly_demand_coverage_percentage: '0.2',
          revenue_coverage_percentage: '0.2',
          estimated_monthly_units: null,
          estimated_monthly_revenue: null,
          currency_code: null,
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
          conclusion_codes: [
            'revenue_blocked_low_monthly_demand',
            'brand_concentration_requires_review',
            'single_root_category_dataset',
          ],
        }}
      />,
    );

    expect(
      screen.getByRole('heading', { name: 'Ready for relative product research' }),
    ).toBeInTheDocument();
    expect(screen.getByText('Not responsible to calculate')).toBeInTheDocument();
    expect(screen.getByLabelText('Largest subcategories')).toHaveTextContent('Cars & Race Cars');
    expect(screen.getByLabelText('Brand concentration')).toHaveTextContent('Hot Wheels');
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
      coverage: [],
      top_categories: [{ label: 'Toys & Games', product_count: 67, product_percentage: '100.0' }],
      top_subcategories: [
        { label: 'Cars & Race Cars', product_count: 40, product_percentage: '59.7' },
      ],
      top_brands: [{ label: 'Hot Wheels', product_count: 20, product_percentage: '29.9' }],
      conclusion_codes: ['revenue_blocked_low_monthly_demand'],
    };
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes('/dashboard/dataset-overview')) return Response.json(categoryOverview);
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
    expect(screen.getByLabelText('Toys & Games ranked products')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Open full category research' })).toHaveAttribute(
      'href',
      expect.stringContaining('category=Toys%20%26%20Games'),
    );
  });
});
