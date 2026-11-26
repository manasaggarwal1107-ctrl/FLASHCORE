import { z } from 'zod';

/**
 * UI sanity limits to prevent accidental huge runs from the browser.
 * ASSUMPTION: confirm real limits with the backend team (API_CONTRACT.md) and adjust here.
 */
export const SIMULATION_LIMITS = {
  maxWorkers: 1_000,
  maxRequestedPurchases: 1_000_000,
  maxTargetInventory: 1_000_000,
} as const;

const wholeNumber = (label: string, max: number) =>
  z.coerce
    .number({ invalid_type_error: `${label} must be a number` })
    .int(`${label} must be a whole number`)
    .min(1, `${label} must be at least 1`)
    .max(max, `${label} cannot exceed ${max.toLocaleString('en-US')}`);

export const simulationSchema = z
  .object({
    strategy: z.string().trim().min(1, 'Select a concurrency strategy'),
    workers: wholeNumber('Workers', SIMULATION_LIMITS.maxWorkers),
    requestedPurchases: wholeNumber('Requested purchases', SIMULATION_LIMITS.maxRequestedPurchases),
    targetInventory: wholeNumber('Target inventory', SIMULATION_LIMITS.maxTargetInventory),
  })
  .refine((v) => v.workers <= v.requestedPurchases, {
    path: ['workers'],
    message: 'Workers cannot exceed requested purchases',
  });

export type SimulationFormValues = z.infer<typeof simulationSchema>;
