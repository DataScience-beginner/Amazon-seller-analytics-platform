import { describe, expect, it } from 'vitest';

import type { ImportDetailApiResponse, ProductListItemResponse } from './contracts';
import { normalizeImportDetail, normalizeProductSummary } from './normalizers';

describe('API normalizers', () => {
  it('preserves a duplicate import underlying status so pending work remains actionable', () => {
    const response: ImportDetailApiResponse = {
      id: 'import-1',
      organisation_id: 'org-1',
      marketplace_id: 'market-1',
      original_filename: 'keepa.xlsx',
      checksum: 'checksum',
      status: 'pending',
      uploaded_at: '2026-07-19T10:00:00Z',
      confirmed_at: null,
      completed_at: null,
      dataset: {
        schema_id: 'keepa.product_finder',
        schema_version: '1.0.0',
        schema_match: 'exact',
        source_column_count: 173,
        registered_column_count: 173,
        matched_column_count: 173,
        new_headers: [],
        missing_headers: [],
        source_header_checksum: 'header-checksum',
        dataset_schema_checksum: 'schema-checksum',
        observed_on: null,
        period_month: null,
        revision: null,
        date_status: 'pending_confirmation',
        observation_date_candidates: [{ date: '2026-05-26', source: 'sheet_name' }],
        observed_on_suggestion: '2026-05-26',
        suggestion_source: 'sheet_name',
        observed_on_source: null,
      },
      workbook: {
        sheet_name: 'Keepa',
        header_row_number: 1,
        alias_registry_version: '1.0.0',
      },
      mapping: {
        registry_id: 'keepa',
        registry_version: '1.0.0',
        columns: [],
        missing_required: ['asin'],
        missing_optional: [],
        requires_confirmation: false,
      },
      preview_rows: [],
      summary: null,
      failure: null,
      duplicate: true,
    };

    expect(normalizeImportDetail(response)).toMatchObject({
      status: 'pending',
      duplicate: true,
      summary: undefined,
      dataset: {
        schema_id: 'keepa.product_finder',
        observed_on_suggestion: '2026-05-26',
      },
    });
  });

  it('does not invent a currency when product evidence omits it', () => {
    const response: ProductListItemResponse = {
      product_id: 'product-1',
      asin: 'B012345678',
      title: null,
      brand: null,
      category: null,
      subcategory: null,
      image_url: null,
      amazon_url: null,
      latest_snapshot_id: 'snapshot-1',
      latest_snapshot_at: '2026-07-19T10:00:00Z',
      latest_observed_on: '2026-05-26',
      buy_box_price: '12.50',
      buy_box_price_90d: null,
      currency_code: null,
      offer_count: null,
      sales_rank: null,
      sales_rank_90d: null,
      estimated_monthly_bought: null,
      buy_box_winner_count_90d: null,
      buy_box_oos_percentage_90d: null,
      demand_score: null,
      competition_score: null,
      price_stability_score: null,
      overall_opportunity_score: null,
      data_confidence_score: null,
      strategy: null,
      recommendation_confidence: null,
      score_formula_version: null,
      strategy_rules_version: null,
      research: null,
      data_quality_codes: ['currency_code_missing'],
    };

    expect(normalizeProductSummary(response).buy_box_price).toEqual({
      amount: '12.50',
      currency_code: null,
    });
  });
});
