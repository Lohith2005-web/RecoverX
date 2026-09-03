/**
 * Formats a monetary number into Indian Rupee string (INR).
 * Options: 'standard' (₹306,024), 'compact' (₹3.06L / ₹1.90Cr).
 */
export function formatINR(val: number | undefined | null, option: 'standard' | 'compact' = 'standard'): string {
  if (val === undefined || val === null || isNaN(val)) {
    return '₹0';
  }

  const num = Number(val);
  const absNum = Math.abs(num);
  const sign = num < 0 ? '-' : '';

  if (option === 'compact') {
    if (absNum >= 10000000) {
      return `${sign}₹${(absNum / 10000000).toFixed(2)}Cr`;
    } else if (absNum >= 100000) {
      return `${sign}₹${(absNum / 100000).toFixed(2)}L`;
    } else if (absNum >= 1000) {
      return `${sign}₹${(absNum / 1000).toFixed(1)}K`;
    }
  }

  return `${sign}₹${Math.round(absNum).toLocaleString('en-IN')}`;
}

/**
 * Formats a percentage value.
 * e.g., 0.1458 -> 14.58%, 5.62 -> +562%
 */
export function formatPercent(val: number | undefined | null, isRatio = false, includeSign = false): string {
  if (val === undefined || val === null || isNaN(val)) {
    return '0.0%';
  }

  const percentVal = isRatio ? val * 100 : val;
  const formatted = percentVal.toFixed(1);
  const sign = includeSign && percentVal > 0 ? '+' : '';
  return `${sign}${formatted}%`;
}
