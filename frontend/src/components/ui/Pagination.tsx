import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from './Button';
import { formatInteger } from '@/lib/format';

export interface PaginationProps {
  page: number; // 1-based
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
}

export function pageCount(total: number, pageSize: number): number {
  return Math.max(1, Math.ceil(total / Math.max(1, pageSize)));
}

export function Pagination({ page, pageSize, total, onPageChange }: PaginationProps) {
  const pages = pageCount(total, pageSize);
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(total, page * pageSize);
  return (
    <nav aria-label="Pagination" className="flex items-center justify-between gap-3 border-t border-line px-4 py-2.5 text-xs text-ink-muted">
      <span className="num">
        {formatInteger(from)}–{formatInteger(to)} of {formatInteger(total)}
      </span>
      <div className="flex items-center gap-2">
        <span className="num hidden sm:inline">
          Page {page} / {pages}
        </span>
        <Button size="sm" variant="ghost" aria-label="Previous page" disabled={page <= 1} onClick={() => onPageChange(page - 1)} icon={<ChevronLeft className="h-3.5 w-3.5" />} />
        <Button size="sm" variant="ghost" aria-label="Next page" disabled={page >= pages} onClick={() => onPageChange(page + 1)} icon={<ChevronRight className="h-3.5 w-3.5" />} />
      </div>
    </nav>
  );
}
