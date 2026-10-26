import { describe, expect, it } from 'vitest';
import { formatDateTime } from '@app/shared-util';

describe('format helpers', () => {
  it('shows one instant in each person’s time zone', () => {
    expect(formatDateTime('2026-10-24T20:30:00.000Z', 'Asia/Kolkata')).toBe('2026-10-25 02:00');
    expect(formatDateTime('2026-10-24T20:30:00.000Z', 'America/New_York')).toBe('2026-10-24 16:30');
  });
});
