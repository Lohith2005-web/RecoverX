import { describe, it, expect } from 'vitest';
import { formatINR, formatPercent } from './formatters';

describe('RecoverX Frontend Formatters', () => {
  it('formats INR standard currency values accurately', () => {
    expect(formatINR(306024.29)).toBe('₹3,06,024');
    expect(formatINR(0)).toBe('₹0');
    expect(formatINR(null)).toBe('₹0');
    expect(formatINR(undefined)).toBe('₹0');
  });

  it('formats INR compact currency values for Lakhs and Crores', () => {
    expect(formatINR(306024.29, 'compact')).toBe('₹3.06L');
    expect(formatINR(19060000, 'compact')).toBe('₹1.91Cr');
    expect(formatINR(5500, 'compact')).toBe('₹5.5K');
  });

  it('formats percentage values cleanly with optional signs', () => {
    expect(formatPercent(14.58)).toBe('14.6%');
    expect(formatPercent(0.1458, true)).toBe('14.6%');
    expect(formatPercent(562, false, true)).toBe('+562.0%');
    expect(formatPercent(0)).toBe('0.0%');
  });
});
