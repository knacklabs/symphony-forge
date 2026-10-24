import { describe, expect, it } from 'vitest';
import { formatDateTime, formatMoney } from '@app/shared';

describe('format helpers', () => {
  it('shows one instant in each person’s time zone', () => {
    expect(formatDateTime('2026-10-24T20:30:00.000Z', 'Asia/Kolkata')).toBe('2026-10-25 02:00');
    expect(formatDateTime('2026-10-24T20:30:00.000Z', 'America/New_York')).toBe('2026-10-24 16:30');
  });

  it('shows cents as money and refuses part of a cent', () => {
    expect(formatMoney(123456)).toBe('USD 1,234.56');
    expect(formatMoney(-5)).toBe('USD -0.05');
    expect(() => formatMoney(1.5)).toThrow(RangeError);
  });
});
