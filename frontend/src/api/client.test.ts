import { describe, expect, it, vi } from 'vitest';

import { ApiError, request } from './client';

describe('API client', () => {
  it('turns the structured backend envelope into an actionable ApiError', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              error: {
                code: 'validation_error',
                message: 'The request could not be validated',
                correlation_id: 'correlation-123',
                details: { fields: [{ field: 'body.file', message: 'File is required' }] },
              },
            }),
            {
              status: 422,
              headers: {
                'content-type': 'application/json',
                'x-correlation-id': 'correlation-123',
              },
            },
          ),
      ),
    );

    const failure = await request('/example').catch((error: unknown) => error);

    expect(failure).toBeInstanceOf(ApiError);
    expect(failure).toMatchObject({
      status: 422,
      code: 'validation_error',
      message: 'The request could not be validated',
      requestId: 'correlation-123',
    });
  });

  it('serializes JSON commands and preserves caller headers', async () => {
    const fetchMock = vi.fn<(input: RequestInfo | URL, options?: RequestInit) => Promise<Response>>(
      async () => Response.json({ ok: true }),
    );
    vi.stubGlobal('fetch', fetchMock);

    await request('/example', {
      method: 'POST',
      headers: { 'x-client': 'selleros' },
      body: { answer: 42 },
    });

    const [, options] = fetchMock.mock.calls[0] ?? [];
    expect(options?.body).toBe('{"answer":42}');
    expect(new Headers(options?.headers).get('content-type')).toBe('application/json');
    expect(new Headers(options?.headers).get('x-client')).toBe('selleros');
  });
});
