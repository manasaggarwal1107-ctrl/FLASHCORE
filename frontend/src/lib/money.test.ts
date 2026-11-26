import { addDecimals, formatMoney, parseDecimal } from './money';

const f = (v: string | number | null | undefined, c: string | null | undefined) =>
  formatMoney(v, c, { locale: 'en-US' });

describe('formatMoney', () => {
  it('formats decimal strings with grouping and currency', () => {
    expect(f('1234.5', 'USD')).toBe('$1,234.50');
    expect(f('0.1', 'USD')).toBe('$0.10');
  });

  it('rounds half away from zero without floating point drift', () => {
    expect(f('1999.999', 'USD')).toBe('$2,000.00');
    expect(f('0.005', 'USD')).toBe('$0.01');
    expect(f('0.004', 'USD')).toBe('$0.00');
    expect(f('-12.345', 'USD')).toBe('-$12.35');
  });

  it('does not show a negative zero', () => {
    expect(f('-0.001', 'USD')).toBe('$0.00');
  });

  it('keeps precision beyond Number.MAX_SAFE_INTEGER', () => {
    expect(f('9007199254740993.10', 'USD')).toBe('$9,007,199,254,740,993.10');
  });

  it('respects zero-decimal currencies', () => {
    expect(f('1500', 'JPY')).toBe('\u00A5' + '1,500');
  });

  it('returns an em dash for missing or malformed values', () => {
    expect(f(null, 'USD')).toBe('\u2014');
    expect(f(undefined, 'USD')).toBe('\u2014');
    expect(f('abc', 'USD')).toBe('\u2014');
    expect(f('1e5', 'USD')).toBe('\u2014');
  });

  it('does not throw on an invalid currency code', () => {
    expect(f('12.5', 'NOPE')).toBe('12.50');
  });

  it('supports plain (symbol-less) output', () => {
    expect(formatMoney('1234.5', 'USD', { locale: 'en-US', plain: true })).toBe('1,234.50');
  });
});

describe('addDecimals', () => {
  it('adds exactly', () => {
    expect(addDecimals('0.1', '0.2')).toBe('0.3');
    expect(addDecimals('10.50', '-0.75')).toBe('9.75');
    expect(addDecimals('1', '-2.5')).toBe('-1.5');
  });

  it('returns null for invalid input', () => {
    expect(addDecimals('x', '1')).toBeNull();
  });
});

describe('parseDecimal', () => {
  it('parses plain decimals and rejects exponents', () => {
    expect(parseDecimal(' 5 ')).toEqual({ negative: false, integer: '5', fraction: '' });
    expect(parseDecimal('1e5')).toBeNull();
    expect(parseDecimal(Number.NaN)).toBeNull();
  });
});