import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AppShell } from '../components/AppShell';

const workspace = {
  organisation_id: 'org-1',
  organisation_name: 'Acme Sellers',
  marketplaces: [
    {
      id: 'market-1',
      code: 'IN',
      name: 'Amazon India',
      default_currency_code: 'INR',
    },
  ],
};

function importResponse(status: 'pending' | 'completed') {
  const canonicalColumns = Array.from({ length: 21 }, (_, index) => ({
    ordinal: index + 1,
    header: index === 0 ? 'ASIN' : index === 1 ? 'Product Title' : `Canonical ${index + 1}`,
    normalized_header:
      index === 0 ? 'asin' : index === 1 ? 'product title' : `canonical ${index + 1}`,
    canonical_field: index === 0 ? 'asin' : index === 1 ? 'title' : `field_${index + 1}`,
    classification: index === 0 ? 'required' : 'optional',
    dataset_classification: 'registered_source',
    candidates: [index === 0 ? 'asin' : index === 1 ? 'title' : `field_${index + 1}`],
    required_candidates: index === 0 ? ['asin'] : [],
    is_required: index === 0,
    samples: index === 0 ? ['B012345678'] : index === 1 ? ['Travel Mug'] : [],
  }));
  const preservedColumns = Array.from({ length: 152 }, (_, index) => ({
    ordinal: index + 22,
    header: `Keepa Source Field ${index + 1}`,
    normalized_header: `keepa source field ${index + 1}`,
    canonical_field: null,
    classification: 'unknown',
    dataset_classification: 'registered_source',
    candidates: [],
    required_candidates: [],
    is_required: false,
    samples: [],
  }));

  return {
    id: 'import-1',
    organisation_id: 'org-1',
    marketplace_id: 'market-1',
    original_filename: 'keepa.xlsx',
    checksum: 'abc123',
    status,
    uploaded_at: '2026-07-19T10:00:00Z',
    confirmed_at: status === 'completed' ? '2026-07-19T10:01:00Z' : null,
    completed_at: status === 'completed' ? '2026-07-19T10:01:02Z' : null,
    dataset: {
      schema_id: 'keepa.product_finder',
      schema_version: '1.0.0',
      schema_match: 'exact',
      source_column_count: 173,
      registered_column_count: 173,
      matched_column_count: 173,
      new_headers: [],
      missing_headers: [],
      source_header_checksum: 'source-header-checksum',
      dataset_schema_checksum: 'dataset-schema-checksum',
      observed_on: status === 'completed' ? '2026-05-26' : null,
      period_month: status === 'completed' ? '2026-05-01' : null,
      revision: status === 'completed' ? 1 : null,
      date_status: status === 'completed' ? 'confirmed' : 'pending_confirmation',
      observation_date_candidates: [{ date: '2026-05-26', source: 'sheet_name' }],
      observed_on_suggestion: '2026-05-26',
      suggestion_source: 'sheet_name',
      observed_on_source: status === 'completed' ? 'user_confirmed' : null,
    },
    workbook: {
      sheet_name: '2026-05-26',
      header_row_number: 1,
      alias_registry_version: '1.0.0',
    },
    mapping: {
      registry_id: 'keepa',
      registry_version: '1.0.0',
      columns: [...canonicalColumns, ...preservedColumns],
      missing_required: [],
      missing_optional: [],
      requires_confirmation: false,
    },
    preview_rows: [
      {
        row_number: 2,
        values: { ASIN: 'B012345678', 'Product Title': 'Travel Mug' },
        issues: [],
      },
    ],
    summary:
      status === 'completed'
        ? {
            total: 4999,
            created: 4999,
            matched: 0,
            skipped: 0,
            failed: 0,
            row_error_count: 0,
          }
        : null,
    failure: null,
    duplicate: false,
  };
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

describe('Keepa import workflow', () => {
  beforeEach(() => {
    window.history.replaceState({}, '', '/imports');
    vi.stubGlobal('scrollTo', vi.fn());
  });

  it('uploads, saves a reviewed mapping, confirms, and displays the transactional summary', async () => {
    const fetchMock = vi.fn<(input: RequestInfo | URL, options?: RequestInit) => Promise<Response>>(
      async (input, options) => {
        const url = new URL(String(input), window.location.origin);
        const method = options?.method ?? 'GET';
        if (url.pathname.endsWith('/health')) {
          return json({ status: 'ok', application: 'SellerOS', database: 'ok' });
        }
        if (url.pathname.endsWith('/workspaces')) return json({ items: [workspace] });
        if (url.pathname.endsWith('/imports') && method === 'GET') return json({ items: [] });
        if (url.pathname.endsWith('/imports') && method === 'POST') {
          expect(options?.body).toBeInstanceOf(FormData);
          const form = options?.body as FormData;
          expect(form.get('organisation_id')).toBe('org-1');
          expect(form.get('marketplace_id')).toBe('market-1');
          expect((form.get('file') as File).name).toBe('keepa.xlsx');
          return json(importResponse('pending'), 201);
        }
        if (url.pathname.endsWith('/imports/import-1/confirm') && method === 'POST') {
          expect(url.searchParams.get('organisation_id')).toBe('org-1');
          expect(url.searchParams.get('marketplace_id')).toBe('market-1');
          expect(JSON.parse(String(options?.body))).toEqual({ observed_on: '2026-05-26' });
          return json(importResponse('completed'));
        }
        if (url.pathname.endsWith('/imports/import-1') && method === 'GET') {
          expect(url.searchParams.get('organisation_id')).toBe('org-1');
          expect(url.searchParams.get('marketplace_id')).toBe('market-1');
          return json(importResponse('pending'));
        }
        throw new Error(`Unexpected request: ${method} ${url}`);
      },
    );
    vi.stubGlobal('fetch', fetchMock);

    render(<AppShell />);

    const fileInput = await screen.findByLabelText(/Keepa Excel file/);
    fireEvent.change(fileInput, {
      target: {
        files: [
          new File(['synthetic workbook'], 'keepa.xlsx', {
            type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
          }),
        ],
      },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Upload and inspect' }));

    expect(
      await screen.findByRole('heading', { name: 'Create the monthly dataset' }),
    ).toBeInTheDocument();
    const dateInput = screen.getByLabelText('Dataset date (observed on)');
    expect(dateInput).toHaveValue('2026-05-26');
    expect(screen.getByText('Canonical fields').nextElementSibling).toHaveTextContent('21');
    expect(screen.getByText('Preserved source fields').nextElementSibling).toHaveTextContent('152');
    expect(screen.getByText('New fields').nextElementSibling).toHaveTextContent('0');
    expect(
      screen.getByText(
        'Every source column is handled by the registered dataset model. No manual mapping is required.',
      ),
    ).toBeInTheDocument();
    expect(screen.queryByLabelText(/SellerOS handling for/)).not.toBeInTheDocument();

    const confirmButton = screen.getByRole('button', { name: 'Create May 2026 dataset' });
    expect(confirmButton).toBeDisabled();
    fireEvent.click(
      screen.getByRole('checkbox', {
        name: /I confirm this workbook contains market evidence observed on/,
      }),
    );
    await waitFor(() => expect(confirmButton).toBeEnabled());
    fireEvent.click(confirmButton);

    expect(
      await screen.findByRole('heading', { name: 'May 2026 dataset created' }),
    ).toBeInTheDocument();
    expect(screen.getByText('New products').nextElementSibling).toHaveTextContent('4,999');
    expect(
      screen.getByText('Dataset confirmed. Previous monthly snapshots remain unchanged.'),
    ).toBeInTheDocument();
  });

  it('labels a completed legacy import as undated without presenting upload time as observed', async () => {
    window.history.replaceState({}, '', '/imports/import-1');
    const legacy = importResponse('completed');
    legacy.dataset.observed_on = null;
    legacy.dataset.period_month = null;
    legacy.dataset.revision = null;
    legacy.dataset.date_status = 'legacy_unconfirmed';
    legacy.dataset.observed_on_source = null;

    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = new URL(String(input), window.location.origin);
        if (url.pathname.endsWith('/health')) {
          return json({ status: 'ok', application: 'SellerOS', database: 'ok' });
        }
        if (url.pathname.endsWith('/workspaces')) return json({ items: [workspace] });
        if (url.pathname.endsWith('/imports/import-1')) return json(legacy);
        throw new Error(`Unexpected request: ${url}`);
      }),
    );

    render(<AppShell />);

    expect(
      await screen.findByRole('heading', {
        name: 'Legacy dataset — observation date unavailable',
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', {
        name: 'Legacy dataset — observation date unavailable',
      }).nextElementSibling,
    ).toHaveTextContent('No observation date was recorded for this historical import.');
    expect(screen.getByText('Observed on').nextElementSibling).toHaveTextContent(
      'Observation date unavailable',
    );
  });
});
