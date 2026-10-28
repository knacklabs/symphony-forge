export function csvField(value: string | number | null): string {
  if (value === null) return '';
  // A spreadsheet runs text that starts with one of these as a formula, so the export keeps it as text.
  const text = typeof value === 'string' && /^[=+\-@]/.test(value) ? `'${value}` : String(value);
  return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}
