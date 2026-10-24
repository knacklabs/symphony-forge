import type { Response } from 'express';

export type CsvColumn<T> = { header: string; value: (row: T) => string | number | null };

function csvField(value: string | number | null): string {
  if (value === null) return '';
  // A spreadsheet runs text that starts with one of these as a formula, so the export keeps it as text.
  const text = typeof value === 'string' && /^[=+\-@]/.test(value) ? `'${value}` : String(value);
  return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

/** The one place that writes CSV. A date column passes formatDateTime(value, 'UTC') and ends its header with " (UTC)". */
export function sendCsv<T>(response: Response, filename: string, columns: CsvColumn<T>[], rows: T[]): void {
  // ponytail: builds the whole file in memory, fine for the constitution's size of app; stream it when a table passes about 50,000 rows.
  const lines = [columns.map(({ header }) => csvField(header)), ...rows.map((row) => columns.map(({ value }) => csvField(value(row))))];
  response.setHeader('Content-Type', 'text/csv; charset=utf-8');
  response.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
  response.send(lines.map((fields) => `${fields.join(',')}\r\n`).join(''));
}
