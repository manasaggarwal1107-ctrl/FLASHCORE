import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Play } from 'lucide-react';
import { FormField, Input, Select } from '@/components/ui/Field';
import { Panel, PanelBody, PanelHeader } from '@/components/ui/Panel';
import { Badge } from '@/components/ui/Badge';
import { FormFooter } from '@/features/shared/FormFooter';
import { useEndpointMutation } from '@/hooks/useEndpointMutation';
import { useResource } from '@/hooks/useResource';
import { endpoints } from '@/services/api/endpoints';
import type { Collection, SimulationRun, StrategyOption } from '@/types/api';
import { simulationSchema } from './simulationSchema';
import type { SimulationFormValues } from './simulationSchema';

export function SimulationForm({ onStarted }: { onStarted: (run: SimulationRun) => void }) {
  const strategies = useResource<Collection<StrategyOption>>(endpoints.concurrency.strategies);
  const start = useEndpointMutation<SimulationFormValues, SimulationRun>(endpoints.concurrency.start, { invalidatePrefixes: ['concurrency.runs'] });
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<SimulationFormValues>({ resolver: zodResolver(simulationSchema) });

  const options = strategies.data?.items ?? [];

  return (
    <Panel>
      <PanelHeader title="Simulation configuration" description="Configure and launch a simulated purchase load." badge={<Badge tone="simulation">Simulation</Badge>} />
      <PanelBody>
        <form
          noValidate
          onSubmit={handleSubmit((values) =>
            // Not retried automatically: a start request may launch a run. Users must re-submit deliberately.
            start.mutate(values, { onSuccess: (run) => onStarted(run) }),
          )}
          className="space-y-4"
        >
          <FormField
            label="Concurrency strategy"
            error={errors.strategy?.message}
            hint={!strategies.live ? 'Strategy list is not connected yet (awaiting API contract).' : strategies.isError ? 'Could not load strategies.' : undefined}
          >
            {(p) => (
              <Select {...p} disabled={!strategies.live || strategies.isPending} {...register('strategy')}>
                <option value="">{strategies.live && strategies.isPending ? 'Loading…' : 'Select strategy'}</option>
                {options.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.label ?? o.id}
                  </option>
                ))}
              </Select>
            )}
          </FormField>
          <div className="grid gap-4 sm:grid-cols-3">
            <FormField label="Concurrent workers" error={errors.workers?.message}>
              {(p) => <Input {...p} inputMode="numeric" {...register('workers')} />}
            </FormField>
            <FormField label="Requested purchases" error={errors.requestedPurchases?.message}>
              {(p) => <Input {...p} inputMode="numeric" {...register('requestedPurchases')} />}
            </FormField>
            <FormField label="Target inventory" error={errors.targetInventory?.message} hint="Units available to the simulated sale">
              {(p) => <Input {...p} inputMode="numeric" {...register('targetInventory')} />}
            </FormField>
          </div>
          <FormFooter
            live={start.live}
            capability={endpoints.concurrency.start.label}
            submitting={start.isPending}
            error={start.error}
            success={start.isSuccess}
            submitLabel="Run simulation"
          />
          <p className="-mt-2 flex items-center gap-1.5 text-xs text-ink-faint">
            <Play className="h-3 w-3" aria-hidden /> Runs are never retried automatically.
          </p>
        </form>
      </PanelBody>
    </Panel>
  );
}
