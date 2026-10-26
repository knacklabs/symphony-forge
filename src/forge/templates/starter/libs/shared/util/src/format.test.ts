import { describe, expect, it } from 'vitest';
import { DEFAULT_CURRENCY, formatMoney } from './index';

// Audit: this pure-logic table owns precision, currency digits and invalid input.
// Float conversion loses large-value precision; fixed digits break JPY and KWD.
// Init/sync owns delivery; these cases exercise the real helper without a test seam.
describe('format helpers', () => {
  it("formats exact decimal money with each currency's own fraction digits", () => {
    expect(DEFAULT_CURRENCY).toBe('INR');
    for (const [amount, currency, expected] of [
      ['1234.5600', 'USD', 'USD 1,234.56'],
      ['-0.0500', 'USD', 'USD -0.05'],
      ['1234', 'JPY', 'JPY 1,234'],
      ['12345678901234.5650', 'USD', 'USD 12,345,678,901,234.57'],
      ['1.2345', 'KWD', 'KWD 1.235'],
    ]) {
      expect(formatMoney(amount, currency)).toBe(expected);
    }
  });

  it('refuses malformed money and currency codes', () => {
    for (const [amount, currency] of [
      ['1.5', 'usd'], ['1,5', 'USD'], ['', 'USD'], ['1e3', 'USD'],
      [' 1', 'USD'], ['1.', 'USD'], ['1', 'US'], ['1', 'USDD'],
    ]) {
      expect(() => formatMoney(amount, currency)).toThrow(RangeError);
    }
  });
});
