import type { ReactNode } from 'react';
import { MISSING } from '@/lib/format';

export interface DetailItem {
  label: string;
  value: ReactNode;
  mono?: boolean;
}

/** Definition grid. Null / empty values render an em dash, never a blank or a default. */
export function DetailList({ items, columns = 3 }: { items: DetailItem[]; columns?: 2 | 3 | 4 }) {
  const grid = columns === 2 ? 'sm:grid-cols-2' : columns === 4 ? 'sm:grid-cols-2 lg:grid-cols-4' : 'sm:grid-cols-2 lg:grid-cols-3';
  return (
    <dl className={`grid grid-cols-1 gap-x-6 gap-y-4 ${grid}`}>
      {items.map((it) => (
        <div key={it.label} className="min-w-0">
          <dt className="eyebrow">{it.label}</dt>
          <dd className={`mt-1 break-words text-sm text-ink ${it.mono ? 'font-mono text-xs' : ''}`}>
            {it.value === null || it.value === undefined || it.value === '' ? <span className="text-ink-faint">{MISSING}</span> : it.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}
