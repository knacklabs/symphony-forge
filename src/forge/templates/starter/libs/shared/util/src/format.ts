// The constitution's default formats: dates as YYYY-MM-DD, 24-hour times and money from whole cents.
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

// ponytail: every currency shows two decimals, change this when the app takes a currency without cents.
export function formatMoney(cents: number, currency = 'USD'): string {
  if (!Number.isInteger(cents)) throw new RangeError('Money must be a whole number of cents.');
  return `${currency} ${formatNumber(cents / 100, 2)}`;
}
