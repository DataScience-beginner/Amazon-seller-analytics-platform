import { describe, expect, it } from 'vitest';

import {
  formatDate,
  formatMonth,
  formatMoney,
  formatUnitMoney,
  formatUtcDate,
  formatUtcDateInput,
} from './format';

describe('exact presentation formatting', () => {
  it('formats the maximum Numeric(16,2) value without binary-float rounding', () => {
    const formatted = formatMoney({
      amount: '99999999999999.99',
      currency_code: 'INR',
    });

    expect(formatted.replace(/\D/g, '')).toBe('9999999999999999');
    expect(formatted).not.toContain('100,000,000,000,000');
  });

  it('rounds display precision directly from the decimal string', () => {
    const formatted = formatMoney({ amount: '1.005', currency_code: 'INR' });

    expect(formatted.replace(/[^\d.]/g, '')).toBe('1.01');
  });

  it('keeps distinct four-decimal supplier unit quotes visibly distinct', () => {
    const first = formatUnitMoney({ amount: '1.0049', currency_code: 'INR' });
    const second = formatUnitMoney({ amount: '1.0001', currency_code: 'INR' });

    expect(first.replace(/[^\d.]/g, '')).toBe('1.0049');
    expect(second.replace(/[^\d.]/g, '')).toBe('1.0001');
    expect(first).not.toBe(second);
  });

  it('treats YYYY-MM-DD as a calendar date without a timezone shift', () => {
    const expected = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(
      new Date(2026, 0, 1),
    );

    expect(formatDate('2026-01-01')).toBe(expected);
    expect(formatDate('2026-01-01')).not.toContain(':');
  });

  it('formats a dataset month without exposing an artificial day or time', () => {
    const expected = new Intl.DateTimeFormat(undefined, {
      month: 'long',
      year: 'numeric',
    }).format(new Date(2026, 4, 1));

    expect(formatMonth('2026-05-01')).toBe(expected);
    expect(formatMonth('2026-05')).toBe(expected);
  });

  it('derives supplier date defaults from the UTC calendar even across positive-offset hours', () => {
    const indiaNextCalendarDayInstant = new Date('2026-05-25T20:00:00Z');

    expect(formatUtcDateInput(indiaNextCalendarDayInstant)).toBe('2026-05-25');
  });

  it('renders UTC source dates without applying the browser timezone', () => {
    const expected = new Intl.DateTimeFormat(undefined, {
      dateStyle: 'medium',
      timeZone: 'UTC',
    }).format(new Date('2026-01-01T00:00:00Z'));

    expect(formatUtcDate('2026-01-01T00:00:00Z')).toBe(expected);
  });
});
