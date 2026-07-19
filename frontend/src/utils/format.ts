import type { MoneyValue } from '../api/contracts';

export function formatDate(value?: string | null): string {
  if (!value) return 'Not available';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

export function formatNumber(value?: number | null, maximumFractionDigits = 1): string {
  if (value === undefined || value === null || !Number.isFinite(value)) return 'Not available';
  return new Intl.NumberFormat(undefined, { maximumFractionDigits }).format(value);
}

export function formatMoney(value: MoneyValue | number | string | null | undefined): string {
  if (value === undefined || value === null || value === '') return 'Not available';
  const amount = typeof value === 'object' ? Number(value.amount) : Number(value);
  const currency = typeof value === 'object' ? value.currency_code : null;
  if (!Number.isFinite(amount)) return String(typeof value === 'object' ? value.amount : value);
  if (!currency) {
    return `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(amount)} (currency unavailable)`;
  }
  try {
    return new Intl.NumberFormat(undefined, {
      style: 'currency',
      currency,
      maximumFractionDigits: 2,
    }).format(amount);
  } catch {
    return `${currency} ${amount.toFixed(2)}`;
  }
}

export function humanize(value: string): string {
  return value.replace(/[_-]+/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}
