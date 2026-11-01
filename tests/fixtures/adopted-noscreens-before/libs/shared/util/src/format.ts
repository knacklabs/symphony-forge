// The constitution's default formats: dates as YYYY-MM-DD, 24-hour times and exact decimal money.
// An app whose constitution chooses other formats changes them here, and only here.
// With no timeZone the runtime's zone is used, which in the browser is the person's zone; the API passes 'UTC'.

function dateTimeParts(value: string | Date, timeZone?: string): Record<string, string> {
  const formatter = new Intl.DateTimeFormat('en-US', {
    timeZone, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  });
  return Object.fromEntries(formatter.formatToParts(new Date(value)).map(({ type, value: part }) => [type, part]));
}

export function formatDate(value: string | Date, timeZone?: string): string {
  const { year, month, day } = dateTimeParts(value, timeZone);
  return `${year}-${month}-${day}`;
}

export function formatTime(value: string | Date, timeZone?: string): string {
  const { hour, minute } = dateTimeParts(value, timeZone);
  return `${hour}:${minute}`;
}

export function formatDateTime(value: string | Date, timeZone?: string): string {
  return `${formatDate(value, timeZone)} ${formatTime(value, timeZone)}`;
}

export function formatNumber(value: number, fractionDigits = 0): string {
  return new Intl.NumberFormat('en-US', { minimumFractionDigits: fractionDigits, maximumFractionDigits: fractionDigits }).format(value);
}

export const DEFAULT_CURRENCY = 'INR';

export function formatMoney(amount: string, currency: string): string {
  if (typeof amount !== 'string' || !/^-?\d+(\.\d+)?$/.test(amount)) throw new RangeError('Money must be a decimal string.');
  if (typeof currency !== 'string' || !/^[A-Z]{3}$/.test(currency)) throw new RangeError('Currency must be three capital letters.');
  const fractionDigits = new Intl.NumberFormat('en-US', { style: 'currency', currency })
    .resolvedOptions().maximumFractionDigits;
  const formatter = new Intl.NumberFormat('en-US', {
    minimumFractionDigits: fractionDigits, maximumFractionDigits: fractionDigits,
  });
  // Intl accepts exact decimal strings; the ES2022 types only declare numbers and bigints.
  const format = formatter.format as (value: string | number | bigint) => string;
  return `${currency} ${format(amount)}`;
}
