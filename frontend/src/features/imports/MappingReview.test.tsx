import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import type { ImportColumnMapping } from '../../api/contracts';
import { MappingReview } from './MappingReview';

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
    header: 'Locale',
    canonical_field: null,
    classification: 'unknown',
    dataset_classification: 'registered_source',
  },
  {
    ordinal: 3,
    header: 'New Keepa Metric',
    canonical_field: null,
    classification: 'unknown',
    dataset_classification: 'unrecognized',
    samples: ['sample'],
  },
];

describe('MappingReview', () => {
  it('keeps registered fields collapsed and exposes only new fields for mapping', () => {
    const onMappingChange = vi.fn();
    render(
      <MappingReview
        columns={columns}
        canonicalFields={['asin', 'title']}
        mappings={{ '1': 'asin', '2': '', '3': '' }}
        missingRequired={[]}
        unresolvedAmbiguous={[]}
        mappingSaved
        saving={false}
        onMappingChange={onMappingChange}
        onSave={vi.fn()}
      />,
    );

    expect(screen.getByText('Canonical decision fields (1)')).toBeInTheDocument();
    expect(screen.getByText('Preserved source fields (1)')).toBeInTheDocument();
    expect(screen.getByLabelText('SellerOS handling for New Keepa Metric')).toBeInTheDocument();
    expect(screen.queryByLabelText('SellerOS handling for Locale')).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('SellerOS handling for New Keepa Metric'), {
      target: { value: 'title' },
    });
    expect(onMappingChange).toHaveBeenCalledWith(3, 'title');
  });
});
