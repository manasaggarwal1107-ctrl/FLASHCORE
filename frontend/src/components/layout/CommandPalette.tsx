import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CornerDownLeft, Search } from 'lucide-react';
import { AnimatePresence, motion } from 'framer-motion';

import { cn } from '@/lib/cn';
import { useOptionalAuth } from '@/hooks/useAuth';
import { allNavItems, getNavGroupsForRole } from './nav';
import type { NavItem } from './nav';

export function filterNavItems(
  query: string,
  items: NavItem[] = allNavItems,
): NavItem[] {
  const q = query.trim().toLowerCase();

  if (!q) return items;

  return items.filter(
    (item) =>
      item.label.toLowerCase().includes(q) ||
      item.keywords?.some((keyword) => keyword.includes(q)),
  );
}

export function CommandPalette({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const navigate = useNavigate();
  const auth = useOptionalAuth();

  const [query, setQuery] = useState('');
  const [index, setIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const availableItems = useMemo(
    () =>
      auth?.user
        ? getNavGroupsForRole(auth.user.role).flatMap((group) => group.items)
        : allNavItems,
    [auth?.user?.role],
  );

  const results = useMemo(
    () => filterNavItems(query, availableItems),
    [query, availableItems],
  );

  useEffect(() => {
    if (open) {
      setQuery('');
      setIndex(0);

      const timeout = setTimeout(() => inputRef.current?.focus(), 0);

      return () => clearTimeout(timeout);
    }
  }, [open]);

  useEffect(() => {
    setIndex((current) => Math.min(current, Math.max(0, results.length - 1)));
  }, [results.length]);

  const go = (item: NavItem | undefined) => {
    if (!item) return;

    navigate(item.path);
    onClose();
  };

  const onKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'Escape') {
      onClose();
    } else if (event.key === 'ArrowDown') {
      event.preventDefault();
      setIndex((current) =>
        Math.min(current + 1, Math.max(0, results.length - 1)),
      );
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setIndex((current) => Math.max(current - 1, 0));
    } else if (event.key === 'Enter') {
      event.preventDefault();
      go(results[index]);
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-[60] flex items-start justify-center bg-canvas/70 px-4 pt-[15vh]"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.12 }}
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) onClose();
          }}
        >
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label="Command search"
            onKeyDown={onKeyDown}
            className="w-full max-w-lg overflow-hidden rounded-lg border border-line-strong bg-surface-overlay shadow-overlay"
            initial={{ y: -8, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: -8, opacity: 0 }}
            transition={{ duration: 0.14 }}
          >
            <div className="flex items-center gap-2.5 border-b border-line px-3.5">
              <Search className="h-4 w-4 text-ink-faint" aria-hidden />

              <input
                ref={inputRef}
                value={query}
                onChange={(event) => {
                  setQuery(event.target.value);
                  setIndex(0);
                }}
                role="combobox"
                aria-expanded="true"
                aria-controls="command-results"
                aria-label="Search pages"
                placeholder="Jump to a page..."
                className="h-12 flex-1 bg-transparent text-sm text-ink placeholder:text-ink-faint focus-visible:ring-0 focus-visible:ring-offset-0"
              />

              <kbd className="rounded border border-line-strong px-1.5 py-0.5 font-mono text-2xs text-ink-faint">
                esc
              </kbd>
            </div>

            <ul
              id="command-results"
              role="listbox"
              className="max-h-72 overflow-y-auto p-1.5"
            >
              {results.length === 0 && (
                <li className="px-3 py-6 text-center text-xs text-ink-muted">
                  No matching pages
                </li>
              )}

              {results.map((item, itemIndex) => (
                <li
                  key={item.path}
                  role="option"
                  aria-selected={itemIndex === index}
                >
                  <button
                    type="button"
                    onMouseEnter={() => setIndex(itemIndex)}
                    onClick={() => go(item)}
                    className={cn(
                      'flex h-9 w-full items-center gap-2.5 rounded px-2.5 text-left text-sm',
                      itemIndex === index
                        ? 'bg-accent/10 text-accent'
                        : 'text-ink-muted',
                    )}
                  >
                    <item.icon className="h-4 w-4" aria-hidden />
                    <span className="flex-1">{item.label}</span>

                    {itemIndex === index && (
                      <CornerDownLeft className="h-3.5 w-3.5" aria-hidden />
                    )}
                  </button>
                </li>
              ))}
            </ul>

            <p className="border-t border-line px-3.5 py-2 text-2xs normal-case tracking-normal text-ink-faint">
              Page navigation only. Record search is not connected until the API contract defines a search endpoint.
            </p>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
