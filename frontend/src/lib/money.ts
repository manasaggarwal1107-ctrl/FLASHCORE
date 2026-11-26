/**
 * Decimal-safe money formatting.
 *
 * Monetary values are expected from the API as decimal STRINGS (e.g. "1999.90").
 * They are parsed into a BigInt of minor units and never pass through floating point,
 * so values such as "0.1" + rounding never drift. Numbers are tolerated for convenience
 * but are converted with toFixed and should be avoided for money.
 */

export const MISSING = '\u2014';

const DECIMAL_RE = /^(-)?(\d+)(?:\.(\d+))?$/;

interface ParsedDecimal {
  negative: boolean;
  integer: string;
  fraction: string;
}

export function parseDecimal(value: string | number | null | undefined): ParsedDecimal | null {
  if (value === null || value === undefined) return null;
  let text: string;
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) return null;
    text = value.toFixed(10).replace(/\.?0+$/, '');
  } else {
    text = value.trim();
  }
  const match = DECIMAL_RE.exec(text);
  if (!match) return null;
  return { negative: match[1] === '-', integer: match[2] ?? '0', fraction: match[3] ?? '' };
}

/** Round half away from zero to `digits` fraction digits using BigInt arithmetic. */
function roundToDigits(p: ParsedDecimal, digits: number): { negative: boolean; integer: bigint; fraction: string } {
  const padded = p.fraction.padEnd(digits, '0');
  const kept = padded.slice(0, digits);
  const nextDigit = padded.charAt(digits);
  let scaled = BigInt(p.integer + kept);
  if (nextDigit !== '' && nextDigit >= '5') scaled += 1n;
  const base = 10n ** BigInt(digits);
  const integer = scaled / base;
  const fraction = digits === 0 ? '' : (scaled % base).toString().padStart(digits, '0');
  const isZero = scaled === 0n;
  return { negative: p.negative && !isZero, integer, fraction };
}

export interface MoneyFormatOptions {
  locale?: string;
  /** Hide the currency symbol (useful in tables with a currency column). */
  plain?: boolean;
}

export function formatMoney(
  value: string | number | null | undefined,
  currency: string | null | undefined,
  options: MoneyFormatOptions = {},
): string {
  const parsed = parseDecimal(value);
  if (!parsed) return MISSING;
  const { locale, plain } = options;

  let formatter: Intl.NumberFormat;
  try {
    formatter = new Intl.NumberFormat(locale, currency ? { style: 'currency', currency } : { style: 'decimal' });
  } catch {
    // Invalid currency code from the API: fall back to a plain number plus the raw code.
    formatter = new Intl.NumberFormat(locale, { style: 'decimal' });
    currency = null;
  }
  const digits = currency
  ? (formatter.resolvedOptions().maximumFractionDigits ?? 2)
  : Math.max(2, Math.min(parsed.fraction.length, 8));
  const rounded = roundToDigits(parsed, digits);
  const groupedInteger = new Intl.NumberFormat(locale, { useGrouping: true }).format(rounded.integer);

  // Use a sample to learn the locale's currency symbol position / separators.
  const template = formatter.formatToParts(-1234.5);
  let out = '';
  let integerEmitted = false;
  for (const part of template) {
    switch (part.type) {
      case 'minusSign':
        if (rounded.negative) out += part.value;
        break;
      case 'integer':
      case 'group':
        if (!integerEmitted) {
          out += groupedInteger;
          integerEmitted = true;
        }
        break;
      case 'decimal':
        if (rounded.fraction) out += part.value;
        break;
      case 'fraction':
        out += rounded.fraction;
        break;
      case 'currency':
        if (!plain) out += part.value;
        break;
      default:
        out += part.value;
    }
  }
  if (!currency && !rounded.fraction) return out.trim();
  if (!currency && rounded.fraction && !template.some((t) => t.type === 'fraction')) {
    out += `.${rounded.fraction}`;
  }
  return out.trim();
}

/** Add two decimal strings exactly (same-currency only; caller's responsibility). */
export function addDecimals(a: string, b: string): string | null {
  const pa = parseDecimal(a);
  const pb = parseDecimal(b);
  if (!pa || !pb) return null;
  const scale = Math.max(pa.fraction.length, pb.fraction.length);
  const toScaled = (p: ParsedDecimal) => {
    const v = BigInt(p.integer + p.fraction.padEnd(scale, '0'));
    return p.negative ? -v : v;
  };
  const sum = toScaled(pa) + toScaled(pb);
  const negative = sum < 0n;
  const abs = (negative ? -sum : sum).toString().padStart(scale + 1, '0');
  const int = abs.slice(0, abs.length - scale) || '0';
  const frac = scale ? abs.slice(abs.length - scale) : '';
  return `${negative ? '-' : ''}${int}${frac ? `.${frac}` : ''}`;
}
