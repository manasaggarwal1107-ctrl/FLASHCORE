import type { ReactNode } from 'react';
import { ArrowDown, ArrowUp } from 'lucide-react';
import { cn } from '@/lib/cn';

export interface Column<T> {
  id: string;
  header: string;
  cell: (row: T) => ReactNode;
  align?: 'left' | 'right';
  /** Backend sort key. Omit for non-sortable columns. */
  sortKey?: string;
  className?: string;
  /** Hide below the `md` breakpoint to keep mobile tables usable. */
  hideOnMobile?: boolean;
}

export interface SortState {
  sort?: string;
  order?: 'asc' | 'desc';
}

export interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  caption: string;
  sort?: SortState;
  onSortChange?: (next: SortState) => void;
  onRowClick?: (row: T) => void;
}

export function DataTable<T>({ columns, rows, rowKey, caption, sort, onSortChange, onRowClick }: DataTableProps<T>) {
  const toggleSort = (key: string) => {
    if (!onSortChange) return;
    if (sort?.sort !== key) onSortChange({ sort: key, order: 'asc' });
    else if (sort.order === 'asc') onSortChange({ sort: key, order: 'desc' });
    else onSortChange({});
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="border-b border-line bg-surface-raised/50">
            {columns.map((col) => {
              const active = col.sortKey && sort?.sort === col.sortKey;
              const ariaSort = active ? (sort?.order === 'desc' ? 'descending' : 'ascending') : col.sortKey ? 'none' : undefined;
              return (
                <th
                  key={col.id}
                  scope="col"
                  aria-sort={ariaSort}
                  className={cn(
                    'whitespace-nowrap px-4 py-2 text-2xs font-medium uppercase text-ink-faint',
                    col.align === 'right' ? 'text-right' : 'text-left',
                    col.hideOnMobile && 'hidden md:table-cell',
                  )}
                >
                  {col.sortKey && onSortChange ? (
                    <button
                      type="button"
                      onClick={() => toggleSort(col.sortKey as string)}
                      className={cn('inline-flex items-center gap-1 uppercase transition-colors hover:text-ink', active && 'text-accent')}
                    >
                      {col.header}
                      {active && (sort?.order === 'desc' ? <ArrowDown className="h-3 w-3" aria-hidden /> : <ArrowUp className="h-3 w-3" aria-hidden />)}
                    </button>
                  ) : (
                    col.header
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {rows.map((row) => (
            <tr
              key={rowKey(row)}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              onKeyDown={
                onRowClick
                  ? (e) => {
                      if (e.key === 'Enter') onRowClick(row);
                    }
                  : undefined
              }
              tabIndex={onRowClick ? 0 : undefined}
              className={cn('transition-colors hover:bg-surface-raised/60', onRowClick && 'cursor-pointer')}
            >
              {columns.map((col) => (
                <td
                  key={col.id}
                  className={cn('px-4 py-2.5 align-middle text-ink', col.align === 'right' ? 'num text-right' : 'text-left', col.hideOnMobile && 'hidden md:table-cell', col.className)}
                >
                  {col.cell(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
