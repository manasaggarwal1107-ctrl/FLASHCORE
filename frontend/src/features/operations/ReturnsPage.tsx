import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Check, RotateCcw, X } from 'lucide-react';

import { StatusBadge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { FormField, Input, Select } from '@/components/ui/Field';
import { PageHeader } from '@/components/ui/PageHeader';
import { Panel, PanelBody, PanelHeader } from '@/components/ui/Panel';
import { listOrders } from '@/services/api/commerceApi';
import { expansionApi } from '@/services/api/expansionApi';

export function ReturnsPage() {
  const qc = useQueryClient();
  const [orderId, setOrderId] = useState('');
  const [returnType, setReturnType] = useState<'return' | 'exchange'>('return');
  const [condition, setCondition] = useState<'good' | 'unopened' | 'damaged' | 'defective'>('good');
  const [reason, setReason] = useState('');
  const [err, setErr] = useState<string | null>(null);

  const returnsQ = useQuery({ queryKey: ['returns'], queryFn: expansionApi.listReturns });
  const ordersQ = useQuery({ queryKey: ['returns.orders'], queryFn: () => listOrders({ status: 'PAID' }) });

  const selectedOrder = ordersQ.data?.items.find((o) => o.id === orderId) ?? ordersQ.data?.items[0];

  const createMut = useMutation({
    mutationFn: () => {
      const firstLine = selectedOrder?.lines[0];
      if (!selectedOrder || !firstLine) throw new Error('Select a paid order with items.');
      return expansionApi.createReturn({
        order_id: Number(selectedOrder.id),
        return_type: returnType,
        reason,
        items: [{ order_item_id: firstLine.id, quantity: 1, condition }],
      });
    },
    onSuccess: () => { setReason(''); setErr(null); void qc.invalidateQueries({ queryKey: ['returns'] }); },
    onError: (e: Error) => setErr(e.message),
  });

  const reviewMut = useMutation({
    mutationFn: ({ id, decision, restock }: { id: string; decision: 'COMPLETED' | 'REJECTED'; restock: boolean }) =>
      expansionApi.reviewReturn(id, { decision, restock_approved: restock, trigger_refund: false }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['returns'] }),
    onError: (e: Error) => setErr(e.message),
  });

  return (
    <div className="space-y-4">
      <PageHeader title="Returns & Exchanges" description="Condition-checked return inspection, controlled restocking, and GST credit notes." />
      {err && <div role="alert" className="rounded border border-danger/40 bg-danger/10 px-3 py-2 text-xs text-danger">{err}</div>}

      <Panel>
        <PanelHeader title="Create Return / Exchange Request" badge={<RotateCcw className="h-4 w-4 text-accent" />} />
        <PanelBody className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <FormField label="Paid Order">{(p) => (
            <Select {...p} value={selectedOrder?.id ?? ''} onChange={(e) => setOrderId(e.target.value)}>
              {(ordersQ.data?.items ?? []).map((o) => <option key={o.id} value={o.id}>{o.reference} (₹{o.total})</option>)}
            </Select>
          )}</FormField>
          <FormField label="Type">{(p) => (
            <Select {...p} value={returnType} onChange={(e) => setReturnType(e.target.value as 'return' | 'exchange')}>
              <option value="return">Return</option>
              <option value="exchange">Exchange</option>
            </Select>
          )}</FormField>
          <FormField label="Inspected Condition">{(p) => (
            <Select {...p} value={condition} onChange={(e) => setCondition(e.target.value as typeof condition)}>
              <option value="unopened">Unopened</option>
              <option value="good">Good</option>
              <option value="damaged">Damaged (Quarantine)</option>
              <option value="defective">Defective (Quarantine)</option>
            </Select>
          )}</FormField>
          <FormField label="Reason">{(p) => <Input {...p} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Size mismatch" />}</FormField>
          <div className="sm:col-span-2 lg:col-span-4">
            <Button variant="primary" disabled={!selectedOrder || reason.trim().length < 3} loading={createMut.isPending} onClick={() => createMut.mutate()}>
              Submit Return Request
            </Button>
          </div>
        </PanelBody>
      </Panel>

      <Panel>
        <PanelHeader title="Return Queue" />
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-line text-ink-faint">
              <tr><th className="p-3">Return #</th><th className="p-3">Order</th><th className="p-3">Condition</th><th className="p-3">Amount</th><th className="p-3">Status</th><th className="p-3">Inspection Decision</th></tr>
            </thead>
            <tbody>
              {(returnsQ.data ?? []).map((r) => (
                <tr key={r.id} className="border-b border-line/60">
                  <td className="p-3 font-mono">{r.returnNumber}</td>
                  <td className="p-3 font-mono">{r.orderNumber}</td>
                  <td className="p-3">{r.condition}</td>
                  <td className="p-3 num">₹{r.refundAmount}</td>
                  <td className="p-3"><StatusBadge status={r.status} /></td>
                  <td className="p-3 flex flex-wrap gap-1.5">
                    {r.status === 'REQUESTED' && (
                      <>
                        <Button size="sm" variant="primary" icon={<Check className="h-3 w-3" />} onClick={() => reviewMut.mutate({ id: r.id, decision: 'COMPLETED', restock: r.condition === 'good' || r.condition === 'unopened' })}>
                          Complete {r.condition === 'good' || r.condition === 'unopened' ? '& Restock' : '(Quarantine)'}
                        </Button>
                        <Button size="sm" variant="danger" icon={<X className="h-3 w-3" />} onClick={() => reviewMut.mutate({ id: r.id, decision: 'REJECTED', restock: false })}>
                          Reject
                        </Button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}
