import { Zap } from 'lucide-react';
import { cn } from '@/lib/cn';

export function Logo({
  collapsed = false,
  surface = 'sidebar',
  className,
}: {
  collapsed?: boolean;
  surface?: 'sidebar' | 'workspace';
  className?: string;
}) {
  const isSidebar = surface === 'sidebar';

  return (
    <div className={cn('flex items-center gap-2.5', className)}>
      <div
        className={cn(
          'flex h-8 w-8 shrink-0 items-center justify-center rounded-md border',
          isSidebar
            ? 'border-sidebar-accent/30 bg-sidebar-accent/10'
            : 'border-accent/30 bg-accent/10',
        )}
      >
        <Zap
          className={cn('h-4 w-4', isSidebar ? 'text-sidebar-accent' : 'text-accent')}
          aria-hidden
        />
      </div>
      {!collapsed && (
        <div className="min-w-0 leading-none">
          <div
            className={cn(
              'text-[15px] font-bold tracking-[0.14em]',
              isSidebar ? 'text-sidebar-ink' : 'text-ink',
            )}
          >
            FLASHCORE
          </div>
          <div
            className={cn(
              'mt-1 truncate text-2xs normal-case tracking-normal',
              isSidebar ? 'text-sidebar-faint' : 'text-ink-faint',
            )}
          >
            Precision at the speed of demand
          </div>
        </div>
      )}
      {collapsed && <span className="sr-only">FLASHCORE</span>}
    </div>
  );
}
