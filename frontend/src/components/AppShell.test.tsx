import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { AppShell } from './AppShell';

describe('AppShell', () => {
  it('renders navigation and health status', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => Response.json({ status: 'ok', application: 'SellerOS', database: 'ok' })),
    );

    render(<AppShell />);

    expect(screen.getByRole('heading', { name: /SellerOS command centre/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Dashboard' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Products' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Planning' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Imports' })).toBeInTheDocument();

    await waitFor(() => expect(screen.getByText(/API ok; database ok/i)).toBeInTheDocument());
  });
});
