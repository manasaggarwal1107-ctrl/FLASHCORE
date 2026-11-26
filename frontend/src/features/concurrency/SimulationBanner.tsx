import { FlaskConical } from 'lucide-react';

/** Persistent notice: lab output is simulation data and must never be read as business data. */
export function SimulationBanner() {
  return (
    <div role="note" className="mb-4 flex items-start gap-3 rounded-md border border-simulation/30 bg-simulation/10 px-4 py-3 text-sm">
      <FlaskConical className="mt-0.5 h-4 w-4 shrink-0 text-simulation" aria-hidden />
      <p className="text-ink-muted">
        <strong className="font-semibold text-simulation">Simulation data.</strong> Everything on this page comes from simulated load runs. It is stored and labelled separately and is never included in
        Overview, Analytics, Orders or Inventory figures.
      </p>
    </div>
  );
}
