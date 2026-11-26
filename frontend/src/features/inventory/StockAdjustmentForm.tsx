import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

import { FormField, Input, Select } from '@/components/ui/Field';
import { FormFooter } from '@/features/shared/FormFooter';
import { apiRequest } from '@/services/api/client';
import { endpoints, isEndpointLive, resolvePath } from '@/services/api/endpoints';

export interface InventoryOption {
  id: string;
  storeId: number | string;
  productId: number | string;
  productName: string | null;
  sku: string | null;
  quantity: number;
  reservedQuantity: number;
}

export const stockAdjustmentSchema = z.object({
  inventoryId: z.string().min(1, 'Select an inventory record'),
  quantityDelta: z.coerce
    .number({ invalid_type_error: 'Enter a whole number' })
    .int('Quantity must be a whole number')
    .refine((n) => n !== 0, 'Adjustment cannot be zero'),
  reason: z.string().trim().min(3, 'Provide a reason (min 3 characters)').max(500),
});

export type StockAdjustmentValues = z.infer<typeof stockAdjustmentSchema>;

export function StockAdjustmentForm({
  inventoryItems,
  onCancel,
}: {
  inventoryItems: InventoryOption[];
  onCancel: () => void;
}) {
  const queryClient = useQueryClient();

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<StockAdjustmentValues>({
    resolver: zodResolver(stockAdjustmentSchema),
    defaultValues: {
      inventoryId: '',
      quantityDelta: 1,
      reason: '',
    },
  });

  const mutation = useMutation<unknown, Error, StockAdjustmentValues>({
    mutationFn: async ({ inventoryId, quantityDelta, reason }) => {
      const endpoint = endpoints.inventory.adjust;

      if (!isEndpointLive(endpoint)) {
        throw new Error('Stock adjustment is not connected.');
      }

      return apiRequest(
        resolvePath(endpoint.path, { inventory_id: inventoryId }),
        {
          method: 'POST',
          body: {
            quantity_delta: quantityDelta,
            reason,
          },
        },
      );
    },

    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: [endpoints.inventory.list.id],
      });
      reset();
    },
  });

  const live = isEndpointLive(endpoints.inventory.adjust);

  return (
    <form
      noValidate
      onSubmit={handleSubmit((values) => mutation.mutate(values))}
      className="space-y-4 p-4"
    >
      <p className="text-xs text-ink-muted">
        Adjusts <strong className="text-ink">physical stock</strong> only.
        Flash-sale allocations remain separate. Every adjustment is recorded
        with its reason.
      </p>

      {inventoryItems.length === 0 ? (
        <p className="text-sm text-ink-muted">
          No inventory records are available to adjust. Create an inventory
          record first.
        </p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-3">
          <FormField
            label="Inventory record"
            error={errors.inventoryId?.message}
          >
            {(p) => (
              <Select {...p} {...register('inventoryId')}>
                <option value="">Select product / store</option>
                {inventoryItems.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.productName ?? `Product ${item.productId}`}
                    {' · Store '}
                    {item.storeId}
                    {' · Stock '}
                    {item.quantity}
                  </option>
                ))}
              </Select>
            )}
          </FormField>

          <FormField
            label="Quantity change"
            error={errors.quantityDelta?.message}
            hint="Use a negative number to remove stock"
          >
            {(p) => (
              <Input
                {...p}
                type="number"
                step="1"
                {...register('quantityDelta')}
              />
            )}
          </FormField>

          <FormField label="Reason" error={errors.reason?.message}>
            {(p) => <Input {...p} {...register('reason')} />}
          </FormField>
        </div>
      )}

      <FormFooter
        live={live && inventoryItems.length > 0}
        capability={endpoints.inventory.adjust.label}
        submitting={mutation.isPending}
        error={mutation.error}
        success={mutation.isSuccess}
        submitLabel="Apply adjustment"
        onCancel={onCancel}
      />
    </form>
  );
}