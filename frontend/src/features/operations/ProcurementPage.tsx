import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { PackageCheck, Plus, Send } from 'lucide-react';

import { StatusBadge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { FormField, Input, Select } from '@/components/ui/Field';
import { PageHeader } from '@/components/ui/PageHeader';
import { Panel, PanelBody, PanelHeader } from '@/components/ui/Panel';
import { listCatalogProducts } from '@/services/api/commerceApi';
import { expansionApi } from '@/services/api/expansionApi';

export function ProcurementPage() {
  const qc = useQueryClient();
  const [supCode, setSupCode] = useState('');
  const [supName, setSupName] = useState('');
  const [supGstin, setSupGstin] = useState('');
  const [supState, setSupState] = useState('27');
  const [poSup, setPoSup] = useState('');
  const [poLoc, setPoLoc] = useState('');
  const [poProd, setPoProd] = useState('');
  const [poQty, setPoQty] = useState('10');
  const [poCostInr, setPoCostInr] = useState('500');
  const [err, setErr] = useState<string | null>(null);

  const suppliersQ = useQuery({ queryKey: ['procurement.suppliers'], queryFn: expansionApi.listSuppliers });
  const posQ = useQuery({ queryKey: ['procurement.pos'], queryFn: expansionApi.listPurchaseOrders });
  const reqsQ = useQuery({ queryKey: ['procurement.reqs'], queryFn: expansionApi.listRequisitions });
  const warehousesQ = useQuery({ queryKey: ['procurement.wh'], queryFn: expansionApi.listWarehouses });
  const productsQ = useQuery({ queryKey: ['procurement.prods'], queryFn: () => listCatalogProducts({}) });

  const createSupplier = useMutation({
    mutationFn: () => expansionApi.createSupplier({ code: supCode, name: supName, gstin: supGstin || undefined, state_code: supState || undefined }),
    onSuccess: () => { setSupCode(''); setSupName(''); setSupGstin(''); setErr(null); void qc.invalidateQueries({ queryKey: ['procurement.suppliers'] }); },
    onError: (e: Error) => setErr(e.message),
  });

  const createPo = useMutation({
    mutationFn: () => expansionApi.createPurchaseOrder({
      supplier_id: Number(poSup || suppliersQ.data?.[0]?.id || 0),
      location_id: Number(poLoc || warehousesQ.data?.[0]?.id || 0),
      items: [{
        product_id: Number(poProd || productsQ.data?.items[0]?.id || 0),
        ordered_quantity: Number(poQty) || 1,
        unit_cost_minor: Math.round((Number(poCostInr) || 0) * 100),
      }],
    }),
    onSuccess: () => { setErr(null); void qc.invalidateQueries({ queryKey: ['procurement.pos'] }); },
    onError: (e: Error) => setErr(e.message),
  });

  const submitPo = useMutation({
    mutationFn: (id: string) => expansionApi.submitPurchaseOrder(id),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['procurement.pos'] }),
    onError: (e: Error) => setErr(e.message),
  });

  const receiveAllPo = useMutation({
    mutationFn: (po: NonNullable<typeof posQ.data>[number]) =>
      expansionApi.receivePurchaseOrder(
        po.id,
        po.items.filter((i) => i.orderedQuantity > i.receivedQuantity).map((i) => ({ item_id: Number(i.id), quantity_received: i.orderedQuantity - i.receivedQuantity })),
        'Received via Procurement Workspace',
      ),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ['procurement.pos'] }); void qc.invalidateQueries({ queryKey: ['warehouses'] }); },
    onError: (e: Error) => setErr(e.message),
  });

  const convertReq = useMutation({
    mutationFn: (id: string) => expansionApi.convertRequisition(id),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ['procurement.reqs'] }); void qc.invalidateQueries({ queryKey: ['procurement.pos'] }); },
    onError: (e: Error) => setErr(e.message),
  });

  return (
    <div className="space-y-4">
      <PageHeader title="Suppliers & Procurement" description="Supplier GSTIN directory, purchase requisitions, purchase orders, and warehouse goods receipt." />
      {err && <div role="alert" className="rounded border border-danger/40 bg-danger/10 px-3 py-2 text-xs text-danger">{err}</div>}

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel>
          <PanelHeader title="Add Supplier" />
          <PanelBody className="grid gap-3 sm:grid-cols-2">
            <FormField label="Code">{(p) => <Input {...p} value={supCode} onChange={(e) => setSupCode(e.target.value)} placeholder="SUP-001" />}</FormField>
            <FormField label="Supplier Name">{(p) => <Input {...p} value={supName} onChange={(e) => setSupName(e.target.value)} placeholder="Deccan Wholesale Pvt Ltd" />}</FormField>
            <FormField label="Supplier GSTIN">{(p) => <Input {...p} value={supGstin} onChange={(e) => setSupGstin(e.target.value.toUpperCase())} placeholder="29AABCD1234F1Z2" />}</FormField>
            <FormField label="State Code">{(p) => <Input {...p} value={supState} onChange={(e) => setSupState(e.target.value)} placeholder="27" />}</FormField>
            <div className="sm:col-span-2">
              <Button variant="primary" icon={<Plus className="h-3.5 w-3.5" />} disabled={!supCode.trim() || !supName.trim()} loading={createSupplier.isPending} onClick={() => createSupplier.mutate()}>
                Add Supplier
              </Button>
            </div>
          </PanelBody>
        </Panel>

        <Panel>
          <PanelHeader title="Create Purchase Order" />
          <PanelBody className="grid gap-3 sm:grid-cols-2">
            <FormField label="Supplier">{(p) => (
              <Select {...p} value={poSup || suppliersQ.data?.[0]?.id || ''} onChange={(e) => setPoSup(e.target.value)}>
                {(suppliersQ.data ?? []).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </Select>
            )}</FormField>
            <FormField label="Destination Location">{(p) => (
              <Select {...p} value={poLoc || warehousesQ.data?.[0]?.id || ''} onChange={(e) => setPoLoc(e.target.value)}>
                {(warehousesQ.data ?? []).map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
              </Select>
            )}</FormField>
            <FormField label="Product">{(p) => (
              <Select {...p} value={poProd || productsQ.data?.items[0]?.id || ''} onChange={(e) => setPoProd(e.target.value)}>
                {(productsQ.data?.items ?? []).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
              </Select>
            )}</FormField>
            <div className="grid grid-cols-2 gap-2">
              <FormField label="Qty">{(p) => <Input {...p} type="number" min={1} value={poQty} onChange={(e) => setPoQty(e.target.value)} />}</FormField>
              <FormField label="Unit Cost ₹">{(p) => <Input {...p} type="number" min={0} value={poCostInr} onChange={(e) => setPoCostInr(e.target.value)} />}</FormField>
            </div>
            <div className="sm:col-span-2">
              <Button variant="primary" icon={<Plus className="h-3.5 w-3.5" />} disabled={(suppliersQ.data?.length ?? 0) === 0 || (productsQ.data?.items.length ?? 0) === 0} loading={createPo.isPending} onClick={() => createPo.mutate()}>
                Create Draft PO
              </Button>
            </div>
          </PanelBody>
        </Panel>
      </div>

      <Panel>
        <PanelHeader title="Supplier Directory" />
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-line text-ink-faint">
              <tr><th className="p-3">Code</th><th className="p-3">Name</th><th className="p-3">GSTIN</th><th className="p-3">Orders</th><th className="p-3">Total Spend</th><th className="p-3">Payable</th></tr>
            </thead>
            <tbody>
              {(suppliersQ.data ?? []).map((s) => (
                <tr key={s.id} className="border-b border-line/60">
                  <td className="p-3 font-mono">{s.code}</td><td className="p-3 font-medium">{s.name}</td><td className="p-3 font-mono">{s.gstin ?? '—'}</td>
                  <td className="p-3 num">{s.orderCount}</td><td className="p-3 num">₹{s.totalSpend}</td><td className="p-3 num">₹{s.outstandingPayable}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel>
        <PanelHeader title="Purchase Orders & Goods Receipt" />
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-line text-ink-faint">
              <tr><th className="p-3">PO #</th><th className="p-3">Supplier</th><th className="p-3">Warehouse</th><th className="p-3">Cost</th><th className="p-3">Status</th><th className="p-3">Action</th></tr>
            </thead>
            <tbody>
              {(posQ.data ?? []).map((po) => (
                <tr key={po.id} className="border-b border-line/60">
                  <td className="p-3 font-mono">{po.poNumber}</td><td className="p-3">{po.supplierName}</td><td className="p-3">{po.locationName}</td>
                  <td className="p-3 num">₹{po.totalCost}</td><td className="p-3"><StatusBadge status={po.status} /></td>
                  <td className="p-3 flex gap-1.5">
                    {po.status === 'DRAFT' && <Button size="sm" icon={<Send className="h-3 w-3" />} onClick={() => submitPo.mutate(po.id)}>Submit</Button>}
                    {(po.status === 'SUBMITTED' || po.status === 'PARTIALLY_RECEIVED') && (
                      <Button size="sm" variant="primary" icon={<PackageCheck className="h-3 w-3" />} onClick={() => receiveAllPo.mutate(po)}>Receive Remaining Goods</Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      {(reqsQ.data?.length ?? 0) > 0 && (
        <Panel>
          <PanelHeader title="Purchase Requisitions" />
          <PanelBody className="space-y-2 text-xs">
            {reqsQ.data?.map((r) => (
              <div key={String(r.id)} className="flex items-center justify-between border-b border-line pb-2">
                <span><strong className="font-mono">{String(r.reqNumber ?? r.req_number)}</strong> — {String(r.status)}</span>
                {r.status === 'PENDING_APPROVAL' && <Button size="sm" onClick={() => convertReq.mutate(String(r.id))}>Approve & Convert to PO</Button>}
              </div>
            ))}
          </PanelBody>
        </Panel>
      )}
    </div>
  );
}
