import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AppShell } from './AppShell';

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

const emptyDashboard = {
  scope: { organisation_id: 'org-1', marketplace_id: 'market-1' },
  tracked_product_count: 0,
  kpis: [
    {
      id: 'tracked_products',
      label: 'Tracked products',
      value: 0,
      unit: 'products',
      definition: 'Products with a latest snapshot.',
    },
  ],
  latest_import: null,
  strategy_distribution: [],
  data_quality_alerts: [],
  top_opportunities: [],
  top_risks: [],
  empty_state: {
    code: 'upload_required',
    title: 'Upload required',
    message: 'Upload a workbook.',
    primary_action: 'open_imports',
  },
};

const datedDashboard = {
  ...emptyDashboard,
  tracked_product_count: 1,
  kpis: [
    {
      id: 'tracked_products',
      label: 'Tracked products',
      value: 1,
      unit: 'products',
      definition: 'Products with a latest snapshot.',
    },
  ],
  latest_import: {
    id: 'import-1',
    original_filename: 'keepa.xlsx',
    status: 'completed',
    uploaded_at: '2026-07-19T10:00:00Z',
    completed_at: '2026-07-19T10:02:00Z',
    observed_on: '2026-05-26',
    period_month: '2026-05-01',
    revision: 1,
    total_rows: 1,
    created_rows: 1,
    matched_rows: 0,
    skipped_rows: 0,
    failed_rows: 0,
  },
  empty_state: null,
};

const readyHealth = {
  status: 'ok',
  application: 'SellerOS',
  database: 'ok',
};

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

describe('AppShell', () => {
  beforeEach(() => {
    window.history.replaceState({}, '', '/dashboard');
    vi.stubGlobal('scrollTo', vi.fn());
  });

  it('loads a scoped dashboard and exposes semantic navigation', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith('/health')) return json(readyHealth);
      if (url.endsWith('/workspaces')) return json({ items: [workspace] });
      if (url.includes('/dashboard?')) return json(emptyDashboard);
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<AppShell />);

    expect(await screen.findByRole('heading', { name: 'Portfolio overview' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Dashboard' })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('link', { name: 'Research' })).toHaveAttribute('href', '/products');
    expect(screen.getByRole('link', { name: 'Imports' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Planning' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Skip to main content' })).toBeInTheDocument();
    expect(screen.getByRole('status', { name: 'System status: verified' })).toHaveTextContent(
      'System verified',
    );
    expect(
      await screen.findByText('Your portfolio is ready for its first import'),
    ).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('organisation_id=org-1&marketplace_id=market-1'),
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it('creates the first workspace and enters the dashboard', async () => {
    let workspacesCreated = false;
    const fetchMock = vi.fn(async (input: RequestInfo | URL, options?: RequestInit) => {
      const url = String(input);
      if (url.endsWith('/health')) return json(readyHealth);
      if (url.endsWith('/workspaces') && options?.method === 'POST') {
        workspacesCreated = true;
        expect(JSON.parse(String(options.body))).toEqual({
          organisation_name: 'Acme Sellers',
          marketplace_code: 'IN',
          marketplace_name: 'Amazon India',
          currency_code: 'INR',
        });
        return json(workspace, 201);
      }
      if (url.endsWith('/workspaces')) return json({ items: [] });
      if (url.includes('/dashboard?')) return json(emptyDashboard);
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<AppShell />);

    expect(
      await screen.findByRole('heading', { name: 'Create a seller workspace' }),
    ).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Organisation name'), {
      target: { value: 'Acme Sellers' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Create workspace' }));

    await waitFor(() => expect(workspacesCreated).toBe(true));
    expect(await screen.findByRole('heading', { name: 'Portfolio overview' })).toBeInTheDocument();
    expect(screen.getByLabelText('Active workspace')).toHaveValue('org-1:market-1');
  });

  it('keeps the latest dataset date separate from its upload timestamp', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith('/health')) return json(readyHealth);
      if (url.endsWith('/workspaces')) return json({ items: [workspace] });
      if (url.includes('/dashboard?')) return json(datedDashboard);
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<AppShell />);

    expect(await screen.findByRole('heading', { name: 'Latest import' })).toBeInTheDocument();
    expect(screen.getByText('Observed on').nextElementSibling).toHaveTextContent('May 26, 2026');
    expect(screen.getByText('Dataset month').nextElementSibling).toHaveTextContent('May 2026');
    expect(screen.getByText('Uploaded').nextElementSibling).toHaveTextContent('Jul 19, 2026');
  });

  it('keeps the loading state until the system health check is verified', async () => {
    let resolveHealth: ((response: Response) => void) | undefined;
    const pendingHealth = new Promise<Response>((resolve) => {
      resolveHealth = resolve;
    });
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith('/health')) return pendingHealth;
      if (url.endsWith('/workspaces')) return json({ items: [workspace] });
      if (url.includes('/dashboard?')) return json(emptyDashboard);
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<AppShell />);

    expect(screen.getByRole('status')).toHaveTextContent(
      'Verifying SellerOS and loading your workspace…',
    );
    expect(
      screen.queryByRole('navigation', { name: 'Primary navigation' }),
    ).not.toBeInTheDocument();

    resolveHealth?.(json(readyHealth));

    expect(await screen.findByRole('heading', { name: 'Portfolio overview' })).toBeInTheDocument();
  });

  it('shows a retryable error when health verification fails', async () => {
    let healthAttempts = 0;
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith('/health')) {
        healthAttempts += 1;
        if (healthAttempts === 1) {
          return json({ status: 'degraded', application: 'SellerOS', database: 'unavailable' });
        }
        return json(readyHealth);
      }
      if (url.endsWith('/workspaces')) return json({ items: [workspace] });
      if (url.includes('/dashboard?')) return json(emptyDashboard);
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<AppShell />);

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'SellerOS is not ready. The application or database health check failed.',
    );
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));

    expect(
      await screen.findByRole('status', { name: 'System status: verified' }),
    ).toBeInTheDocument();
    expect(healthAttempts).toBe(2);
  });

  it('moves focus to main content after client-side navigation', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith('/health')) return json(readyHealth);
      if (url.endsWith('/workspaces')) return json({ items: [workspace] });
      if (url.includes('/dashboard?')) return json(emptyDashboard);
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<AppShell />);

    expect(await screen.findByRole('heading', { name: 'Portfolio overview' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('link', { name: 'Planning' }));

    expect(await screen.findByRole('heading', { name: 'Planning' })).toBeInTheDocument();
    await waitFor(() => expect(document.getElementById('main-content')).toHaveFocus());
  });
});
