import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowRightLeft, Plus } from 'lucide-react';

import { StatusBadge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { FormField, Input, Select } from '@/components/ui/Field';
import { PageHeader } from '@/components/ui/PageHeader';
import { Panel, PanelBody, PanelHeader } from '@/components/ui/Panel';
import { listCatalogProducts } from '@/services/api/commerceApi';
import { expansionApi } from '@/services/api/expansionApi';

export function WarehousesPage() {
  const qc = useQueryClient();
  const [code, setCode] = useState('');
  const [name, setName] = useState('');
  const [locType, setLocType] = useState('store');
  const [city, setCity] = useState('');
  const [stateName, setStateName] = useState('');
  const [trProd, setTrProd] = useState('');
  const [trFrom, setTrFrom] = useState('');
  const [trTo, setTrTo] = useState('');
  const [trQty, setTrQty] = useState('5');
  const [trApproval, setTrApproval] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const warehousesQ = useQuery({ queryKey: ['warehouses'], queryFn: expansionApi.listWarehouses });
  const transfersQ = useQuery({ queryKey: ['transfers'], queryFn: expansionApi.listTransfers });
  const productsQ = useQuery({ queryKey: ['warehouses.products'], queryFn: () => listCatalogProducts({}) });

  const createWh = useMutation({
    mutationFn: () => expansionApi.createWarehouse({ code, name, location_type: locType, city: city || undefined, state: stateName || undefined }),
    onSuccess: () => { setCode(''); setName(''); setErr(null); void qc.invalidateQueries({ queryKey: ['warehouses'] }); },
    onError: (e: Error) => setErr(e.message),
  });

  const createTr = useMutation({
    mutationFn: () => expansionApi.createTransfer({
      product_id: Number(trProd || productsQ.data?.items[0]?.id || 0),
      from_location_id: Number(trFrom),
      to_location_id: Number(trTo),
      quantity: Number(trQty) || 1,
      requires_approval: trApproval,
    }),
    onSuccess: () => { setErr(null); void qc.invalidateQueries({ queryKey: ['transfers'] }); },
    onError: (e: Error) => setErr(e.message),
  });

  const actionTr = useMutation({
    mutationFn: ({ id, op }: { id: string; op: 'approve' | 'dispatch' | 'receive' }) =>
      op === 'approve' ? expansionApi.approveTransfer(id) : op === 'dispatch' ? expansionApi.dispatchTransfer(id) : expansionApi.receiveTransfer(id),
    onSuccess: () => { setErr(null); void qc.invalidateQueries({ queryKey: ['transfers'] }); void qc.invalidateQueries({ queryKey: ['warehouses'] }); },
    onError: (e: Error) => setErr(e.message),
  });

  return (
    <div className="space-y-4">
      <PageHeader title="Warehouses & Stock Transfers" description="Manage multiple warehouses and retail stores with concurrency-safe stock transfers." />
      {err && <div role="alert" className="rounded border border-danger/40 bg-danger/10 px-3 py-2 text-xs text-danger">{err}</div>}

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel>
          <PanelHeader title="Add Warehouse / Store" />
          <PanelBody className="grid gap-3 sm:grid-cols-2">
            <FormField label="Code">{(p) => <Input {...p} value={code} onChange={(e) => setCode(e.target.value)} placeholder="STR-DEL-01" />}</FormField>
            <FormField label="Name">{(p) => <Input {...p} value={name} onChange={(e) => setName(e.target.value)} placeholder="Connaught Place Store" />}</FormField>
            <FormField label="Type">{(p) => (
              <Select {...p} value={locType} onChange={(e) => setLocType(e.target.value)}>
                <option value="warehouse">Warehouse</option>
                <option value="store">Store</option>
                <option value="fulfilment_centre">Fulfilment Centre</option>
              </Select>
            )}</FormField>
            <FormField label="City / State">{(p) => <Input {...p} value={city} onChange={(e) => { setCity(e.target.value); setStateName(e.target.value); }} placeholder="Delhi" />}</FormField>
            <div className="sm:col-span-2">
              <Button variant="primary" icon={<Plus className="h-3.5 w-3.5" />} disabled={!code.trim() || !name.trim()} loading={createWh.isPending} onClick={() => createWh.mutate()}>
                Create Location
              </Button>
            </div>
          </PanelBody>
        </Panel>

        <Panel>
          <PanelHeader title="Initiate Stock Transfer" />
          <PanelBody className="grid gap-3 sm:grid-cols-2">
            <FormField label="Product">{(p) => (
              <Select {...p} value={trProd || productsQ.data?.items[0]?.id || ''} onChange={(e) => setTrProd(e.target.value)}>
                {(productsQ.data?.items ?? []).map((x) => <option key={x.id} value={x.id}>{x.name} ({x.sku})</option>)}
              </Select>
            )}</FormField>
            <FormField label="Quantity">{(p) => <Input {...p} type="number" min={1} value={trQty} onChange={(e) => setTrQty(e.target.value)} />}</FormField>
            <FormField label="From Location">{(p) => (
              <Select {...p} value={trFrom} onChange={(e) => setTrFrom(e.target.value)}>
                <option value="">Select source</option>
                {(warehousesQ.data ?? []).map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
              </Select>
            )}</FormField>
            <FormField label="To Location">{(p) => (
              <Select {...p} value={trTo} onChange={(e) => setTrTo(e.target.value)}>
                <option value="">Select destination</option>
                {(warehousesQ.data ?? []).map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
              </Select>
            )}</FormField>
            <label className="flex items-center gap-2 text-xs text-ink-muted sm:col-span-2">
              <input type="checkbox" checked={trApproval} onChange={(e) => setTrApproval(e.target.checked)} />
              Require manager approval before dispatch
            </label>
            <div className="sm:col-span-2">
              <Button variant="primary" icon={<ArrowRightLeft className="h-3.5 w-3.5" />} disabled={!trFrom || !trTo || trFrom === trTo} loading={createTr.isPending} onClick={() => createTr.mutate()}>
                Create Transfer
              </Button>
            </div>
          </PanelBody>
        </Panel>
      </div>

      <Panel>
        <PanelHeader title="Locations Summary" />
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-line text-ink-faint">
              <tr><th className="p-3">Code</th><th className="p-3">Name</th><th className="p-3">Type</th><th className="p-3">On Hand</th><th className="p-3">Reserved</th><th className="p-3">Damaged</th></tr>
            </thead>
            <tbody>
              {(warehousesQ.data ?? []).map((w) => (
                <tr key={w.id} className="border-b border-line/60">
                  <td className="p-3 font-mono">{w.code}</td><td className="p-3 font-medium">{w.name}</td><td className="p-3">{w.locationType}</td>
                  <td className="p-3 num">{w.totalUnits}</td><td className="p-3 num">{w.reservedUnits}</td><td className="p-3 num">{w.damagedUnits}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel>
        <PanelHeader title="Transfer Ledger" />
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-line text-ink-faint">
              <tr><th className="p-3">Ref</th><th className="p-3">Product</th><th className="p-3">Route</th><th className="p-3">Qty</th><th className="p-3">Status</th><th className="p-3">Actions</th></tr>
            </thead>
            <tbody>
              {(transfersQ.data ?? []).map((t) => (
                <tr key={t.id} className="border-b border-line/60">
                  <td className="p-3 font-mono">{t.transferNumber}</td>
                  <td className="p-3">{t.productName}</td>
                  <td className="p-3">{t.fromLocationName} → {t.toLocationName}</td>
                  <td className="p-3 num">{t.quantity}</td>
                  <td className="p-3"><StatusBadge status={t.status} /></td>
                  <td className="p-3 flex gap-1.5">
                    {t.status === 'PENDING_APPROVAL' && <Button size="sm" onClick={() => actionTr.mutate({ id: t.id, op: 'approve' })}>Approve</Button>}
                    {t.status === 'APPROVED' && <Button size="sm" variant="primary" onClick={() => actionTr.mutate({ id: t.id, op: 'dispatch' })}>Dispatch</Button>}
                    {t.status === 'IN_TRANSIT' && <Button size="sm" variant="primary" onClick={() => actionTr.mutate({ id: t.id, op: 'receive' })}>Receive</Button>}
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
