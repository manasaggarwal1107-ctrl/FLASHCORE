import { Zap } from 'lucide-react';
import { cn } from '@/lib/cn';

export function Logo({ collapsed = false, className }: { collapsed?: boolean; className?: string }) {
  return (
    <div className={cn('flex items-center gap-2.5', className)}>
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-accent/30 bg-accent/10">
        <Zap className="h-4 w-4 text-accent" aria-hidden />
      </div>
      {!collapsed && (
        <div className="min-w-0 leading-none">
          <div className="text-[15px] font-bold tracking-[0.14em] text-ink">FLASHCORE</div>
          <div className="mt-1 truncate text-2xs normal-case tracking-normal text-ink-faint">Precision at the speed of demand</div>
        </div>
      )}
      {collapsed && <span className="sr-only">FLASHCORE</span>}
    </div>
  );
}
