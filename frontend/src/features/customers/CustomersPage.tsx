import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Search } from 'lucide-react';
import { Link } from 'react-router-dom';

import { OriginBadge, StatusBadge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { FormField, Input } from '@/components/ui/Field';
import { PageHeader } from '@/components/ui/PageHeader';
import { Panel, PanelBody, PanelHeader } from '@/components/ui/Panel';
import { useOptionalAuth } from '@/hooks/useAuth';
import { formatDateTime, formatInteger } from '@/lib/format';
import { getActiveOrganisationId } from '@/services/api/auth';
import { createCustomer, listCustomers } from '@/services/api/commerceApi';
import { endpoints } from '@/services/api/endpoints';

export function CustomersPage() {
  const queryClient = useQueryClient();
  const auth = useOptionalAuth();
  const orgId = auth?.activeOrganisation?.organisationId ?? getActiveOrganisationId() ?? null;
  const role = auth?.activeRole ?? 'owner';
  const canEdit = role === 'owner' || role === 'admin' || role === 'operator';

  const [search, setSearch] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: '', email: '', phone: '' });
  const [formError, setFormError] = useState<string | null>(null);

  const customersQuery = useQuery({
    queryKey: [endpoints.customers.list.id, orgId, search],
    queryFn: () => listCustomers({ search: search.trim() || undefined }),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      createCustomer({
        name: form.name.trim(),
        email: form.email.trim() || undefined,
        phone: form.phone.trim() || undefined,
      }),
    onSuccess: () => {
      setForm({ name: '', email: '', phone: '' });
      setFormError(null);
      setShowForm(false);
      void queryClient.invalidateQueries({ queryKey: [endpoints.customers.list.id, orgId] });
    },
    onError: (err: Error) => setFormError(err.message || 'Unable to create customer.'),
  });

  const items = customersQuery.data?.items ?? [];

  return (
    <div className="space-y-4">
      <PageHeader
        title="Customers"
        description="Tenant-scoped customer directory linked to real retail orders and checkout prefill."
        actions={
          canEdit && (
            <Button
              variant="primary"
              icon={<Plus className="h-4 w-4" />}
              onClick={() => {
                setFormError(null);
                setShowForm((prev) => !prev);
              }}
            >
              {showForm ? 'Close form' : 'New customer'}
            </Button>
          )
        }
      />

      {showForm && canEdit && (
        <Panel>
          <PanelHeader title="Add customer" />
          <PanelBody>
            <form
              className="grid gap-3 md:grid-cols-3"
              onSubmit={(e) => {
                e.preventDefault();
                if (!form.name.trim()) {
                  setFormError('Customer name is required.');
                  return;
                }
                createMutation.mutate();
              }}
            >
              <FormField label="Full name">
                {(p) => (
                  <Input
                    {...p}
                    placeholder="Aarav Sharma"
                    value={form.name}
                    onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                  />
                )}
              </FormField>
              <FormField label="Email">
                {(p) => (
                  <Input
                    {...p}
                    type="email"
                    placeholder="aarav@example.com"
                    value={form.email}
                    onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                  />
                )}
              </FormField>
              <FormField label="Phone">
                {(p) => (
                  <Input
                    {...p}
                    placeholder="+919876543210"
                    value={form.phone}
                    onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))}
                  />
                )}
              </FormField>
              {formError && (
                <div role="alert" className="md:col-span-3 rounded border border-danger/40 bg-danger/10 px-3 py-2 text-xs text-danger">
                  {formError}
                </div>
              )}
              <div className="md:col-span-3 flex justify-end gap-2">
                <Button type="button" variant="secondary" onClick={() => setShowForm(false)}>
                  Cancel
                </Button>
                <Button type="submit" variant="primary" loading={createMutation.isPending}>
                  Create customer
                </Button>
              </div>
            </form>
          </PanelBody>
        </Panel>
      )}

      <Panel>
        <PanelBody>
          <div className="mb-4 flex items-center gap-2 rounded border border-line-strong bg-canvas px-3 h-9 max-w-md">
            <Search className="h-4 w-4 text-ink-muted" aria-hidden />
            <input
              type="search"
              aria-label="Search customers"
              placeholder="Search by name, email or reference..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full bg-transparent text-sm text-ink placeholder:text-ink-faint focus:outline-none"
            />
          </div>

          {customersQuery.isLoading ? (
            <p className="text-sm text-ink-muted">Loading customers...</p>
          ) : customersQuery.isError ? (
            <div role="alert" className="rounded border border-danger/40 bg-danger/10 p-3 text-sm text-danger">
              {(customersQuery.error as Error)?.message || 'Failed to load customers.'}
            </div>
          ) : items.length === 0 ? (
            <p className="py-8 text-center text-sm text-ink-muted">
              No customers in this workspace yet.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-line text-xs uppercase text-ink-muted">
                    <th className="py-2 pr-4">Customer</th>
                    <th className="py-2 pr-4">Reference</th>
                    <th className="py-2 pr-4">Contact</th>
                    <th className="py-2 pr-4">Orders</th>
                    <th className="py-2 pr-4">Status</th>
                    <th className="py-2 pr-4">Created</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {items.map((c) => (
                    <tr key={c.id} className="hover:bg-surface-raised/60">
                      <td className="py-3 pr-4">
                        <Link to={`/customers/${c.id}`} className="font-medium text-accent hover:underline">
                          {c.name}
                        </Link>
                        <div className="mt-0.5">
                          <OriginBadge origin={c.origin} />
                        </div>
                      </td>
                      <td className="py-3 pr-4 font-mono text-xs text-ink-muted">{c.reference}</td>
                      <td className="py-3 pr-4 text-xs text-ink-muted">
                        <div>{c.email ?? '—'}</div>
                        <div>{c.phone ?? '—'}</div>
                      </td>
                      <td className="py-3 pr-4 font-mono text-ink">{formatInteger(c.orderCount)}</td>
                      <td className="py-3 pr-4">
                        <StatusBadge status={c.status} />
                      </td>
                      <td className="py-3 pr-4 text-xs text-ink-muted">{formatDateTime(c.createdAt)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </PanelBody>
      </Panel>
    </div>
  );
}
