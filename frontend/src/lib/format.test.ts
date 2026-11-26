import { camelizeKeys } from './case';
import { formatDateTime, formatDurationMs, formatInteger, formatPercent, humanize, safeRatio } from './format';

describe('format helpers', () => {
  it('safeRatio never returns NaN or Infinity', () => {
    expect(safeRatio(1, 0)).toBeNull();
    expect(safeRatio(null, 5)).toBeNull();
    expect(safeRatio(5, undefined)).toBeNull();
    expect(safeRatio(1, 4)).toBe(0.25);
  });

  it('formatPercent handles missing values', () => {
    expect(formatPercent(0.1234)).toBe('12.3%');
    expect(formatPercent(null)).toBe('—');
    expect(formatPercent(Number.NaN)).toBe('—');
  });

  it('formatDurationMs picks sensible units', () => {
    expect(formatDurationMs(0.2)).toBe('<1 ms');
    expect(formatDurationMs(250)).toBe('250 ms');
    expect(formatDurationMs(1500)).toBe('1.50 s');
    expect(formatDurationMs(null)).toBe('—');
  });

  it('formatInteger / formatDateTime tolerate null and invalid input', () => {
    expect(formatInteger(undefined)).toBe('—');
    expect(formatDateTime(null)).toBe('—');
    expect(formatDateTime('not a date')).toBe('—');
  });

  it('humanize converts machine strings', () => {
    expect(humanize('ORDER_PLACED')).toBe('Order placed');
    expect(humanize('in-progress')).toBe('In progress');
    expect(humanize(null)).toBe('—');
  });
});

describe('camelizeKeys', () => {
  it('converts nested snake_case keys and leaves camelCase and values untouched', () => {
    expect(camelizeKeys({ a_b: { c_d_e: [{ f_g: 1 }] }, alreadyCamel: 2 })).toEqual({ aB: { cDE: [{ fG: 1 }] }, alreadyCamel: 2 });
    expect(camelizeKeys([1, 'a_b'])).toEqual([1, 'a_b']);
    expect(camelizeKeys(null)).toBeNull();
  });
});
