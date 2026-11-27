import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Pause, Play, Plus, Tag, Zap } from 'lucide-react';

import { StatusBadge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { FormField, Input, Select } from '@/components/ui/Field';
import { PageHeader } from '@/components/ui/PageHeader';
import { Panel, PanelBody, PanelHeader } from '@/components/ui/Panel';
import { listCatalogProducts } from '@/services/api/commerceApi';
import { expansionApi } from '@/services/api/expansionApi';

export function CampaignsPromotionsPage() {
  const qc = useQueryClient();
  const [cName, setCName] = useState('');
  const [cProd, setCProd] = useState('');
  const [cAlloc, setCAlloc] = useState('25');
  const [cDiscountPct, setCDiscountPct] = useState('15');
  const [cHours, setCHours] = useState('12');

  const [pCode, setPCode] = useState('');
  const [pName, setPName] = useState('');
  const [pType, setPType] = useState<'percentage' | 'fixed'>('percentage');
  const [pValue, setPValue] = useState('1000');
  const [pMinOrder, setPMinOrder] = useState('500');
  const [err, setErr] = useState<string | null>(null);

  const campaignsQ = useQuery({ queryKey: ['campaigns'], queryFn: expansionApi.listCampaigns });
  const promotionsQ = useQuery({ queryKey: ['promotions'], queryFn: expansionApi.listPromotions });
  const productsQ = useQuery({ queryKey: ['campaigns.products'], queryFn: () => listCatalogProducts({}) });

  const createCamp = useMutation({
    mutationFn: () => {
      const now = new Date();
      const end = new Date(now.getTime() + (Number(cHours) || 12) * 3600_000);
      return expansionApi.createCampaign({
        name: cName,
        starts_at: now.toISOString(),
        ends_at: end.toISOString(),
        discount_type: 'percentage',
        discount_value: Math.round((Number(cDiscountPct) || 10) * 100),
        activate_immediately: true,
        products: [{ product_id: Number(cProd || productsQ.data?.items[0]?.id || 0), allocated_units: Number(cAlloc) || 10 }],
      });
    },
    onSuccess: () => { setCName(''); setErr(null); void qc.invalidateQueries({ queryKey: ['campaigns'] }); },
    onError: (e: Error) => setErr(e.message),
  });

  const transitionCamp = useMutation({
    mutationFn: ({ id, target }: { id: string; target: string }) => expansionApi.transitionCampaign(id, target),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['campaigns'] }),
    onError: (e: Error) => setErr(e.message),
  });

  const createPromo = useMutation({
    mutationFn: () => expansionApi.createPromotion({
      code: pCode,
      name: pName,
      discount_type: pType,
      discount_value: Number(pValue) || 500,
      min_order_minor: Math.round((Number(pMinOrder) || 0) * 100),
    }),
    onSuccess: () => { setPCode(''); setPName(''); setErr(null); void qc.invalidateQueries({ queryKey: ['promotions'] }); },
    onError: (e: Error) => setErr(e.message),
  });

  return (
    <div className="space-y-4">
      <PageHeader title="Surge Control & Promotions" description="Live commercial flash-sale campaigns, concurrency-safe allocations, and coupon codes." />
      {err && <div role="alert" className="rounded border border-danger/40 bg-danger/10 px-3 py-2 text-xs text-danger">{err}</div>}

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel>
          <PanelHeader title="Launch Surge Campaign" badge={<Zap className="h-4 w-4 text-accent" />} />
          <PanelBody className="grid gap-3 sm:grid-cols-2">
            <FormField label="Campaign Name">{(p) => <Input {...p} value={cName} onChange={(e) => setCName(e.target.value)} placeholder="Weekend Surge" />}</FormField>
            <FormField label="Eligible Product">{(p) => (
              <Select {...p} value={cProd || productsQ.data?.items[0]?.id || ''} onChange={(e) => setCProd(e.target.value)}>
                {(productsQ.data?.items ?? []).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
              </Select>
            )}</FormField>
            <FormField label="Allocated Units">{(p) => <Input {...p} type="number" min={1} value={cAlloc} onChange={(e) => setCAlloc(e.target.value)} />}</FormField>
            <div className="grid grid-cols-2 gap-2">
              <FormField label="Discount %">{(p) => <Input {...p} type="number" min={1} max={95} value={cDiscountPct} onChange={(e) => setCDiscountPct(e.target.value)} />}</FormField>
              <FormField label="Hours">{(p) => <Input {...p} type="number" min={1} value={cHours} onChange={(e) => setCHours(e.target.value)} />}</FormField>
            </div>
            <div className="sm:col-span-2">
              <Button variant="primary" icon={<Plus className="h-3.5 w-3.5" />} disabled={!cName.trim() || (productsQ.data?.items.length ?? 0) === 0} loading={createCamp.isPending} onClick={() => createCamp.mutate()}>
                Launch Campaign
              </Button>
            </div>
          </PanelBody>
        </Panel>

        <Panel>
          <PanelHeader title="Create Coupon Code" badge={<Tag className="h-4 w-4 text-brand" />} />
          <PanelBody className="grid gap-3 sm:grid-cols-2">
            <FormField label="Coupon Code">{(p) => <Input {...p} value={pCode} onChange={(e) => setPCode(e.target.value.toUpperCase())} placeholder="FESTIVE15" />}</FormField>
            <FormField label="Title">{(p) => <Input {...p} value={pName} onChange={(e) => setPName(e.target.value)} placeholder="Festive Discount" />}</FormField>
            <FormField label="Type">{(p) => (
              <Select {...p} value={pType} onChange={(e) => setPType(e.target.value as 'percentage' | 'fixed')}>
                <option value="percentage">Percentage (bps, 1000=10%)</option>
                <option value="fixed">Fixed (paise, 50000=₹500)</option>
              </Select>
            )}</FormField>
            <div className="grid grid-cols-2 gap-2">
              <FormField label="Value">{(p) => <Input {...p} type="number" min={1} value={pValue} onChange={(e) => setPValue(e.target.value)} />}</FormField>
              <FormField label="Min Order ₹">{(p) => <Input {...p} type="number" min={0} value={pMinOrder} onChange={(e) => setPMinOrder(e.target.value)} />}</FormField>
            </div>
            <div className="sm:col-span-2">
              <Button variant="primary" icon={<Plus className="h-3.5 w-3.5" />} disabled={!pCode.trim() || !pName.trim()} loading={createPromo.isPending} onClick={() => createPromo.mutate()}>
                Create Promotion
              </Button>
            </div>
          </PanelBody>
        </Panel>
      </div>

      <Panel>
        <PanelHeader title="Surge Campaigns" />
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-line text-ink-faint">
              <tr><th className="p-3">Campaign</th><th className="p-3">Status</th><th className="p-3">Units Sold</th><th className="p-3">Paid Orders</th><th className="p-3">Revenue</th><th className="p-3">Controls</th></tr>
            </thead>
            <tbody>
              {(campaignsQ.data ?? []).map((c) => (
                <tr key={c.id} className="border-b border-line/60">
                  <td className="p-3 font-medium">{c.name}</td>
                  <td className="p-3"><StatusBadge status={c.status} /></td>
                  <td className="p-3 num">{c.totalUnitsSold}</td>
                  <td className="p-3 num">{c.ordersGenerated}</td>
                  <td className="p-3 num">₹{c.revenue}</td>
                  <td className="p-3 flex gap-1.5">
                    {c.status === 'ACTIVE' && <Button size="sm" icon={<Pause className="h-3 w-3" />} onClick={() => transitionCamp.mutate({ id: c.id, target: 'PAUSED' })}>Pause</Button>}
                    {c.status === 'PAUSED' && <Button size="sm" variant="primary" icon={<Play className="h-3 w-3" />} onClick={() => transitionCamp.mutate({ id: c.id, target: 'ACTIVE' })}>Resume</Button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel>
        <PanelHeader title="Coupon Promotions" />
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-line text-ink-faint">
              <tr><th className="p-3">Code</th><th className="p-3">Name</th><th className="p-3">Type</th><th className="p-3">Min Order</th><th className="p-3">Used</th></tr>
            </thead>
            <tbody>
              {(promotionsQ.data ?? []).map((pr) => (
                <tr key={pr.id} className="border-b border-line/60">
                  <td className="p-3 font-mono font-semibold text-accent">{pr.code}</td>
                  <td className="p-3">{pr.name}</td>
                  <td className="p-3">{pr.discountType} ({pr.discountValue})</td>
                  <td className="p-3 num">₹{pr.minOrder}</td>
                  <td className="p-3 num">{pr.usedCount}{pr.usageLimit ? ` / ${pr.usageLimit}` : ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}
