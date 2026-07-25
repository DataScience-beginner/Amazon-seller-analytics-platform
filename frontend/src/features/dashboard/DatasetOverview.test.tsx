import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { DatasetOverview } from './DatasetOverview';

describe('DatasetOverview', () => {
  it('blocks revenue when monthly demand coverage is insufficient', () => {
    render(
      <DatasetOverview
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
});
