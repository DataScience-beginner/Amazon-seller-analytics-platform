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
    workbook: {
      sheet_name: 'Products',
      header_row_number: 1,
      alias_registry_version: '1.0.0',
    },
    mapping: {
      registry_id: 'keepa',
      registry_version: '1.0.0',
      columns: [
        {
          ordinal: 1,
          header: 'ASIN',
          normalized_header: 'asin',
          canonical_field: 'asin',
          classification: 'required',
          candidates: ['asin'],
          required_candidates: ['asin'],
          is_required: true,
          samples: ['B012345678'],
        },
        {
          ordinal: 2,
          header: 'Product Title',
          normalized_header: 'product title',
          canonical_field: 'title',
          classification: 'optional',
          candidates: ['title'],
          required_candidates: [],
          is_required: false,
          samples: ['Travel Mug'],
        },
      ],
      missing_required: [],
      missing_optional: [],
      requires_confirmation: status === 'pending',
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
        ? { total: 1, created: 1, matched: 0, skipped: 0, failed: 0, row_error_count: 0 }
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
        const url = new URL(String(input));
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
        if (url.pathname.endsWith('/imports/import-1/mapping') && method === 'PUT') {
          expect(url.searchParams.get('organisation_id')).toBe('org-1');
          expect(url.searchParams.get('marketplace_id')).toBe('market-1');
          expect(JSON.parse(String(options?.body))).toEqual({
            mappings: { '1': 'asin', '2': 'title' },
          });
          return json(importResponse('pending'));
        }
        if (url.pathname.endsWith('/imports/import-1/confirm') && method === 'POST') {
          expect(url.searchParams.get('organisation_id')).toBe('org-1');
          expect(url.searchParams.get('marketplace_id')).toBe('market-1');
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
      await screen.findByRole('heading', { name: 'Confirm column mapping' }),
    ).toBeInTheDocument();
    const confirmButton = screen.getByRole('button', { name: 'Confirm and create snapshots' });
    expect(confirmButton).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Save mapping' }));
    await waitFor(() => expect(confirmButton).toBeEnabled());
    fireEvent.click(confirmButton);

    expect(await screen.findByRole('heading', { name: 'Import summary' })).toBeInTheDocument();
    expect(screen.getByText('New products').nextElementSibling).toHaveTextContent('1');
    expect(
      screen.getByText('Import confirmed. Previous snapshots remain unchanged.'),
    ).toBeInTheDocument();
  });
});
