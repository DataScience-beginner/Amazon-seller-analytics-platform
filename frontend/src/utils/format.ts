import type { MoneyValue } from '../api/contracts';

export function formatUtcDateInput(date = new Date()): string {
  return date.toISOString().slice(0, 10);
}

export function formatUtcDate(value?: string | null): string {
  if (!value) return 'Not available';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeZone: 'UTC',
  }).format(date);
}

export function formatDate(value?: string | null): string {
  if (!value) return 'Not available';
  const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (dateOnly) {
    const [, year, month, day] = dateOnly;
    const localCalendarDate = new Date(Number(year), Number(month) - 1, Number(day));
    if (
      localCalendarDate.getFullYear() !== Number(year) ||
      localCalendarDate.getMonth() !== Number(month) - 1 ||
      localCalendarDate.getDate() !== Number(day)
    ) {
      return value;
    }
    return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(localCalendarDate);
  }
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
  return formatMoneyWithPrecision(value, 2);
}

export function formatUnitMoney(value: MoneyValue | number | string | null | undefined): string {
  return formatMoneyWithPrecision(value, 4);
}

function formatMoneyWithPrecision(
  value: MoneyValue | number | string | null | undefined,
  maximumFractionDigits: number,
): string {
  if (value === undefined || value === null || value === '') return 'Not available';
  const amount = String(typeof value === 'object' ? value.amount : value).trim();
  const currency = typeof value === 'object' ? value.currency_code : null;
  const parsed = /^([+-]?)(\d+)(?:\.(\d+))?$/.exec(amount);
  if (!parsed) return amount;
  const [, sign, integer = '0', decimal = ''] = parsed;
  if (!currency) {
    return `${formatExactDecimal(sign === '-', integer, decimal, 0, maximumFractionDigits)} (currency unavailable)`;
  }
  try {
    const currencyOptions = new Intl.NumberFormat(undefined, {
      style: 'currency',
      currency,
      maximumFractionDigits,
    }).resolvedOptions();
    return formatExactDecimal(
      sign === '-',
      integer,
      decimal,
      currencyOptions.minimumFractionDigits ?? 2,
      currencyOptions.maximumFractionDigits ?? maximumFractionDigits,
      currency,
    );
  } catch {
    return `${currency} ${formatExactDecimal(sign === '-', integer, decimal, 2, maximumFractionDigits)}`;
  }
}

function formatExactDecimal(
  negative: boolean,
  integer: string,
  decimal: string,
  minimumFractionDigits: number,
  maximumFractionDigits: number,
  currency?: string,
): string {
  const scale = 10n ** BigInt(maximumFractionDigits);
  const paddedDecimal = decimal.padEnd(maximumFractionDigits + 1, '0');
  const retainedDecimal = paddedDecimal.slice(0, maximumFractionDigits) || '0';
  let scaled = BigInt(integer) * scale + BigInt(retainedDecimal);
  if ((paddedDecimal[maximumFractionDigits] ?? '0') >= '5') scaled += 1n;

  const whole = scaled / scale;
  let fraction = maximumFractionDigits
    ? String(scaled % scale).padStart(maximumFractionDigits, '0')
    : '';
  while (fraction.length > minimumFractionDigits && fraction.endsWith('0')) {
    fraction = fraction.slice(0, -1);
  }

  const formatter = currency
    ? new Intl.NumberFormat(undefined, {
        style: 'currency',
        currency,
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
      })
    : new Intl.NumberFormat(undefined, {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
      });
  let parts = integerFormatParts(formatter, whole, negative && scaled !== 0n);
  if (fraction) {
    const decimalMark = new Intl.NumberFormat(undefined, {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    })
      .formatToParts(1n)
      .find((part) => part.type === 'decimal')?.value;
    let lastInteger = -1;
    parts.forEach((part, index) => {
      if (part.type === 'integer') lastInteger = index;
    });
    parts = [
      ...parts.slice(0, lastInteger + 1),
      { type: 'decimal', value: decimalMark ?? '.' },
      { type: 'fraction', value: fraction },
      ...parts.slice(lastInteger + 1),
    ];
  }
  return parts.map((part) => part.value).join('');
}

function integerFormatParts(
  formatter: Intl.NumberFormat,
  whole: bigint,
  negative: boolean,
): Intl.NumberFormatPart[] {
  if (!negative || whole !== 0n) return formatter.formatToParts(negative ? -whole : whole);

  const negativeTemplate = formatter.formatToParts(-1n);
  const zeroNumberParts = formatter
    .formatToParts(0n)
    .filter((part) => part.type === 'integer' || part.type === 'group');
  const output: Intl.NumberFormatPart[] = [];
  let numberInserted = false;
  for (const part of negativeTemplate) {
    if (part.type === 'integer' || part.type === 'group') {
      if (!numberInserted) output.push(...zeroNumberParts);
      numberInserted = true;
    } else {
      output.push(part);
    }
  }
  return output;
}

export function humanize(value: string): string {
  return value.replace(/[_-]+/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}
