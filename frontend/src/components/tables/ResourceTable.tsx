import { useState } from 'react';
import type { ReactNode } from 'react';
import { Search } from 'lucide-react';
import { DataTable } from './DataTable';
import type { Column, SortState } from './DataTable';
import { Input, Select } from '@/components/ui/Field';
import { Pagination } from '@/components/ui/Pagination';
import { Panel } from '@/components/ui/Panel';
import { AwaitingContractState, EmptyState, ErrorState } from '@/components/ui/States';
import { TableSkeleton } from '@/components/ui/Skeleton';
import { useDebouncedValue } from '@/hooks/useDebouncedValue';
import { useResourceList } from '@/hooks/useResourceList';
import type { EndpointSpec } from '@/services/api/endpoints';
import { DEFAULT_PAGE_SIZE } from '@/services/api/pagination';

export interface FilterDef {
  key: string;
  label: string;
  /** `select` needs `options`. Use `text` where the valid values are not known to the frontend. */
  type?: 'select' | 'text' | 'date';
  options?: { value: string; label: string }[];
}

/** Shared origin filter: the four origins are fixed by the product rules, not by the API. */
export const originFilter: FilterDef = {
  key: 'origin',
  label: 'Origin',
  type: 'select',
  options: [
    { value: 'real', label: 'Real' },
    { value: 'imported', label: 'Imported' },
    { value: 'manual', label: 'Manual' },
    { value: 'simulation', label: 'Simulation' },
  ],
};

export interface ResourceTableProps<T> {
  endpoint: EndpointSpec;
  columns: Column<T>[];
  rowKey: (row: T) => string;
  caption: string;
  searchPlaceholder?: string;
  /** Omit to hide the search box when the resource is not searchable. */
  searchable?: boolean;
  filters?: FilterDef[];
  emptyTitle?: string;
  emptyDescription?: ReactNode;
  onRowClick?: (row: T) => void;
  toolbarExtra?: ReactNode;
  /** Required when the endpoint path has `:params` (e.g. customer orders). */
  pathParams?: Record<string, string | number>;
  pageSize?: number;
}

/**
 * Reusable searchable / filterable / sortable / paginated table bound to one list endpoint.
 * Handles the five states uniformly: awaiting-contract, loading, error, empty, data.
 */
export function ResourceTable<T>({
  endpoint,
  columns,
  rowKey,
  caption,
  searchPlaceholder = 'Search…',
  searchable = true,
  filters = [],
  emptyTitle,
  emptyDescription,
  onRowClick,
  toolbarExtra,
  pathParams,
  pageSize = DEFAULT_PAGE_SIZE,
}: ResourceTableProps<T>) {
  const [page, setPage] = useState(1);
  const [searchInput, setSearchInput] = useState('');
  const [sort, setSort] = useState<SortState>({});
  const [filterValues, setFilterValues] = useState<Record<string, string>>({});
  const search = useDebouncedValue(searchInput.trim(), 300);

  const activeFilters = Object.fromEntries(Object.entries(filterValues).filter(([, v]) => v !== ''));
  const query = useResourceList<T>(endpoint, { page, pageSize, search: search || undefined, sort: sort.sort, order: sort.order, filters: activeFilters }, pathParams);
  const controlsDisabled = !query.live;
  const hasQueryRefinement = Boolean(search) || Object.keys(activeFilters).length > 0;

  let body: ReactNode;
  if (!query.live) {
    body = <AwaitingContractState capability={endpoint.label} />;
  } else if (query.isPending) {
    body = <TableSkeleton columns={Math.min(columns.length, 6)} />;
  } else if (query.isError) {
    body = <ErrorState error={query.error} onRetry={() => void query.refetch()} />;
  } else if (query.data.items.length === 0) {
    body = (
      <EmptyState
        title={hasQueryRefinement ? 'No matching records' : (emptyTitle ?? 'No records yet')}
        description={hasQueryRefinement ? 'Try changing or clearing the search and filters.' : emptyDescription}
      />
    );
  } else {
    body = (
      <>
        <div className={query.isFetching ? 'opacity-70 transition-opacity' : 'transition-opacity'}>
          <DataTable columns={columns} rows={query.data.items} rowKey={rowKey} caption={caption} sort={sort} onSortChange={(s) => { setSort(s); setPage(1); }} onRowClick={onRowClick} />
        </div>
        <Pagination page={page} pageSize={pageSize} total={query.data.total} onPageChange={setPage} />
      </>
    );
  }

  return (
    <Panel>
      {(searchable || filters.length > 0 || toolbarExtra) && (
        <div className="flex flex-wrap items-center gap-2 border-b border-line p-3">
          {searchable && (
            <div className="relative min-w-[200px] flex-1 sm:max-w-xs">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-faint" aria-hidden />
              <Input
                type="search"
                aria-label={searchPlaceholder}
                placeholder={searchPlaceholder}
                className="pl-8"
                value={searchInput}
                disabled={controlsDisabled}
                onChange={(e) => {
                  setSearchInput(e.target.value);
                  setPage(1);
                }}
              />
            </div>
          )}
          {filters.map((f) => {
            const setValue = (v: string) => {
              setFilterValues((prev) => ({ ...prev, [f.key]: v }));
              setPage(1);
            };
            if (f.type === 'text' || f.type === 'date') {
              return (
                <Input
                  key={f.key}
                  type={f.type === 'date' ? 'date' : 'text'}
                  aria-label={f.label}
                  placeholder={f.label}
                  title={f.label}
                  className="w-auto min-w-[140px] max-w-[180px]"
                  value={filterValues[f.key] ?? ''}
                  disabled={controlsDisabled}
                  onChange={(e) => setValue(e.target.value)}
                />
              );
            }
            return (
              <Select key={f.key} aria-label={f.label} className="w-auto min-w-[140px]" value={filterValues[f.key] ?? ''} disabled={controlsDisabled} onChange={(e) => setValue(e.target.value)}>
                <option value="">{f.label}: all</option>
                {(f.options ?? []).map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </Select>
            );
          })}
          {toolbarExtra && <div className="ml-auto flex items-center gap-2">{toolbarExtra}</div>}
        </div>
      )}
      {body}
    </Panel>
  );
}
