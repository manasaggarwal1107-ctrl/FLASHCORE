import { useState } from 'react';
import type { FormEvent } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Navigate, useNavigate, useParams } from 'react-router-dom';

import { Button } from '@/components/ui/Button';
import { PageHeader } from '@/components/ui/PageHeader';
import { Panel, PanelBody } from '@/components/ui/Panel';
import { apiRequest } from '@/services/api/client';
import { endpoints } from '@/services/api/endpoints';

interface ProductPayload {
  sku: string;
  name: string;
  description: string | null;
}

interface CreatedProduct {
  id: number;
  sku: string;
  name: string;
  description: string | null;
}

export function ProductFormPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [sku, setSku] = useState('');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [errors, setErrors] = useState<{ name?: string; sku?: string }>({});

  const mutation = useMutation({
    mutationFn: (payload: ProductPayload) =>
      apiRequest<CreatedProduct>('/simulations/products', {
        method: 'POST',
        body: payload,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: [endpoints.products.list.id],
      });
      navigate('/products');
    },
  });

  if (id) return <Navigate to="/products" replace />;

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const nextErrors: { name?: string; sku?: string } = {};

    if (!name.trim()) nextErrors.name = 'Name is required';
    if (!sku.trim()) nextErrors.sku = 'SKU is required';

    setErrors(nextErrors);

    if (Object.keys(nextErrors).length > 0) return;

    mutation.mutate({
      sku: sku.trim(),
      name: name.trim(),
      description: description.trim() || null,
    });
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title="New product"
        description="Create a product in the retail simulation catalogue."
      />

      <Panel>
        <PanelBody>
          <form onSubmit={submit} className="max-w-2xl space-y-4">
            <div>
              <label htmlFor="product-name" className="mb-1 block text-sm font-medium">
                Product name
              </label>
              <input
                id="product-name"
                required
                maxLength={200}
                value={name}
                onChange={(event) => {
                  setName(event.target.value);
                  setErrors((previous) => ({ ...previous, name: undefined }));
                }}
                className="min-h-10 w-full rounded-md border border-line bg-surface px-3 text-sm"
              />
              {errors.name && (
                <p className="mt-1 text-sm text-danger">{errors.name}</p>
              )}
            </div>

            <div>
              <label htmlFor="product-sku" className="mb-1 block text-sm font-medium">
                SKU
              </label>
              <input
                id="product-sku"
                required
                maxLength={100}
                value={sku}
                onChange={(event) => {
                  setSku(event.target.value);
                  setErrors((previous) => ({ ...previous, sku: undefined }));
                }}
                className="min-h-10 w-full rounded-md border border-line bg-surface px-3 font-mono text-sm"
              />
              {errors.sku && (
                <p className="mt-1 text-sm text-danger">{errors.sku}</p>
              )}
            </div>

            <div>
              <label htmlFor="product-description" className="mb-1 block text-sm font-medium">
                Description
              </label>
              <textarea
                id="product-description"
                rows={4}
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                className="w-full rounded-md border border-line bg-surface px-3 py-2 text-sm"
              />
            </div>

            {mutation.isError && (
              <p className="text-sm text-danger" role="alert">
                Product creation failed: {mutation.error.message}
              </p>
            )}

            <div className="flex gap-2">
              <Button type="button" variant="secondary" onClick={() => navigate('/products')}>
                Cancel
              </Button>
              <Button type="submit" variant="primary" disabled={mutation.isPending}>
                {mutation.isPending ? 'Creating…' : 'Create product'}
              </Button>
            </div>
          </form>
        </PanelBody>
      </Panel>
    </div>
  );
}