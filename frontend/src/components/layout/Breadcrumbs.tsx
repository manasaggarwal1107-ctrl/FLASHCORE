import { Link, useLocation } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';
import { labelForSegment } from './nav';

export interface Crumb {
  label: string;
  to?: string;
}

/** Pure helper so breadcrumb derivation is unit-testable. */
export function buildCrumbs(pathname: string): Crumb[] {
  const segments = pathname.split('/').filter(Boolean);
  const crumbs: Crumb[] = [];
  segments.forEach((segment, index) => {
    const to = `/${segments.slice(0, index + 1).join('/')}`;
    const isLast = index === segments.length - 1;
    const label = index === 0 ? (labelForSegment(segment) ?? decodeURIComponent(segment)) : decodeURIComponent(segment);
    crumbs.push(isLast ? { label } : { label, to });
  });
  return crumbs;
}

export function Breadcrumbs() {
  const { pathname } = useLocation();
  const crumbs = buildCrumbs(pathname);
  if (crumbs.length === 0) return null;
  return (
    <nav aria-label="Breadcrumb" className="min-w-0">
      <ol className="flex items-center gap-1.5 text-xs text-ink-muted">
        <li className="hidden sm:block">FLASHCORE</li>
        {crumbs.map((c, i) => (
          <li key={`${c.label}-${i}`} className="flex min-w-0 items-center gap-1.5">
            <ChevronRight className="hidden h-3 w-3 text-ink-faint sm:block" aria-hidden />
            {c.to ? (
              <Link to={c.to} className="truncate hover:text-ink">
                {c.label}
              </Link>
            ) : (
              <span aria-current="page" className="truncate font-medium text-ink">
                {c.label}
              </span>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}
