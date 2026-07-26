import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import type { ImportColumnMapping, ImportDatasetMetadata } from '../../api/contracts';
import {
  DatasetConfirmationPanel,
  datasetCounts,
  observedOnError,
} from './DatasetConfirmationPanel';

const columns: ImportColumnMapping[] = [
  {
    ordinal: 1,
    header: 'ASIN',
    canonical_field: 'asin',
    classification: 'required',
    dataset_classification: 'registered_source',
  },
  {
    ordinal: 2,
    header: 'Title',
    canonical_field: 'title',
    classification: 'optional',
    dataset_classification: 'registered_source',
  },
  {
    ordinal: 3,
    header: 'Locale',
    canonical_field: null,
    classification: 'unknown',
    dataset_classification: 'registered_source',
  },
  {
    ordinal: 4,
    header: 'Surprise Metric',
    canonical_field: null,
    classification: 'unknown',
    dataset_classification: 'unrecognized',
  },
];

describe('dated import dataset contract', () => {
  it('separates canonical, preserved and genuinely new source fields', () => {
    expect(datasetCounts(columns)).toEqual({
      canonical: 2,
      preserved: 1,
      unrecognized: 1,
    });
  });

  it('requires a real, non-future observed date', () => {
    expect(observedOnError('', '2026-07-25')).toBe('Choose the date represented by this workbook.');
    expect(observedOnError('2026-02-30', '2026-07-25')).toBe('Enter a valid date.');
    expect(observedOnError('2026-07-26', '2026-07-25')).toBe(
      'Dataset evidence cannot be dated in the future.',
    );
    expect(observedOnError('2026-05-26', '2026-07-25')).toBeNull();
  });

  it('shows conflicting date evidence without choosing between candidates', () => {
    const dataset: ImportDatasetMetadata = {
      schema_id: 'keepa.product_finder',
      schema_version: '1.0.0',
      schema_match: 'compatible',
      source_column_count: 4,
      registered_column_count: 3,
      matched_column_count: 3,
      new_headers: ['Surprise Metric'],
      missing_headers: [],
      source_header_checksum: null,
      dataset_schema_checksum: 'schema-checksum',
      observed_on: null,
      period_month: null,
      revision: null,
      date_status: 'pending_confirmation',
      observed_on_suggestion: null,
      suggestion_source: null,
      observation_date_candidates: [
        { date: '2026-05-26', source: 'sheet_name' },
        { date: '2026-06-01', source: 'filename' },
      ],
      observed_on_source: null,
    };

    render(
      <DatasetConfirmationPanel
        dataset={dataset}
        columns={columns}
        observedOn=""
        today="2026-07-25"
        acknowledged={false}
        mappingReady
        confirming={false}
        actionError={null}
        onObservedOnChange={vi.fn()}
        onAcknowledgedChange={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );

    expect(screen.getByRole('status')).toHaveTextContent(
      'Conflicting workbook dates were detected',
    );
    expect(screen.getByRole('status')).toHaveTextContent('May 26, 2026 (Sheet Name)');
    expect(screen.getByLabelText('Dataset date (observed on)')).toHaveValue('');
  });
});
