import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Download, Play } from 'lucide-react';

import { StatusBadge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Input, Select } from '@/components/ui/Field';
import { PageHeader } from '@/components/ui/PageHeader';
import { Panel, PanelBody, PanelHeader } from '@/components/ui/Panel';
import { expansionApi } from '@/services/api/expansionApi';

const REPORT_TYPES = [
  { id: 'sales', label: 'Sales Report' },
  { id: 'product_performance', label: 'Product Performance' },
  { id: 'inventory', label: 'Inventory Valuation & Stock' },
  { id: 'stock_movements', label: 'Stock Movements' },
  { id: 'customers', label: 'Customer LTV & Segments' },
  { id: 'campaigns', label: 'Campaign Performance' },
  { id: 'payments', label: 'Payments Report' },
  { id: 'refunds', label: 'Refunds Report' },
  { id: 'procurement', label: 'Procurement Report' },
];

export function ReportsHubPage() {
  const qc = useQueryClient();
  const [reportType, setReportType] = useState('sales');
  const [ruleName, setRuleName] = useState('');
  const [ruleTrigger, setRuleTrigger] = useState('low_stock');

  const reportQ = useQuery({ queryKey: ['reports.view', reportType], queryFn: () => expansionApi.getReport(reportType) });
  const intelQ = useQuery({ queryKey: ['reports.inventoryIntel'], queryFn: expansionApi.getInventoryIntelligence });
  const rulesQ = useQuery({ queryKey: ['reports.automationRules'], queryFn: expansionApi.listAutomationRules });
  const readinessQ = useQuery({ queryKey: ['reports.readiness'], queryFn: expansionApi.listReadinessAdapters });

  const createRule = useMutation({
    mutationFn: () => expansionApi.createAutomationRule({ name: ruleName, trigger_type: ruleTrigger, threshold_value: 5 }),
    onSuccess: () => { setRuleName(''); void qc.invalidateQueries({ queryKey: ['reports.automationRules'] }); },
  });

  const runRules = useMutation({
    mutationFn: expansionApi.runAutomationRules,
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['reports.automationRules'] }),
  });

  const intel = intelQ.data as { totalStockValue?: string; lowStockCount?: number; outOfStockCount?: number; note?: string } | undefined;

  return (
    <div className="space-y-4">
      <PageHeader
        title="Reports, Intelligence & Automation"
        description="CSV-safe reports, inventory reorder intelligence, statistical forecast readiness, automation rules, and adapters."
        actions={
          <Button variant="primary" icon={<Download className="h-3.5 w-3.5" />} onClick={() => void expansionApi.downloadReportCsv(reportType)}>
            Export CSV
          </Button>
        }
      />

      <Panel>
        <PanelHeader
          title="Operational Report Explorer"
          actions={
            <Select aria-label="Report type" value={reportType} onChange={(e) => setReportType(e.target.value)} className="w-60">
              {REPORT_TYPES.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}
            </Select>
          }
        />
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-line text-ink-faint">
              <tr>{(reportQ.data?.headers ?? []).map((h) => <th key={h} className="p-3">{h}</th>)}</tr>
            </thead>
            <tbody>
              {(reportQ.data?.rows ?? []).slice(0, 30).map((row, idx) => (
                <tr key={idx} className="border-b border-line/60">
                  {(reportQ.data?.headers ?? []).map((h) => <td key={h} className="p-3">{String(row[h] ?? '')}</td>)}
                </tr>
              ))}
              {(reportQ.data?.rows.length ?? 0) === 0 && (
                <tr><td colSpan={Math.max(1, reportQ.data?.headers.length ?? 1)} className="p-6 text-center text-ink-faint">No matching records for this report yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </Panel>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel>
          <PanelHeader title="Inventory Valuation & Stock Alerts" />
          <PanelBody className="space-y-2 text-xs">
            <div>Total Stock Valuation: <strong className="num text-accent">₹{String(intel?.totalStockValue ?? '0.00')}</strong></div>
            <div>Low Stock SKUs: <strong className="num">{String(intel?.lowStockCount ?? 0)}</strong> · Out of Stock: <strong className="num">{String(intel?.outOfStockCount ?? 0)}</strong></div>
            {intel?.note && <p className="text-ink-faint">{intel.note}</p>}
          </PanelBody>
        </Panel>

        <Panel>
          <PanelHeader
            title="Automation Rules"
            actions={<Button size="sm" icon={<Play className="h-3 w-3" />} onClick={() => runRules.mutate()}>Run Now</Button>}
          />
          <PanelBody className="space-y-3">
            <div className="flex gap-2">
              <Input placeholder="Rule name..." value={ruleName} onChange={(e) => setRuleName(e.target.value)} />
              <Select value={ruleTrigger} onChange={(e) => setRuleTrigger(e.target.value)} className="w-44">
                <option value="low_stock">Low Stock Alert</option>
                <option value="campaign_expiry">Campaign Expiry</option>
                <option value="pending_po">Pending PO Receipt</option>
              </Select>
              <Button size="sm" disabled={!ruleName.trim()} onClick={() => createRule.mutate()}>Add</Button>
            </div>
            {(rulesQ.data ?? []).map((r) => (
              <div key={String(r.id)} className="flex items-center justify-between text-xs border-b border-line/60 pb-1.5">
                <span>{String(r.name)} ({String(r.triggerType ?? r.trigger_type)})</span>
                <StatusBadge status={String(r.lastStatus ?? r.last_status ?? 'ACTIVE')} />
              </div>
            ))}
          </PanelBody>
        </Panel>
      </div>

      <Panel>
        <PanelHeader title="India Compliance, Hardware & Omnichannel Readiness" />
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-line text-ink-faint">
              <tr><th className="p-3">Adapter</th><th className="p-3">Category</th><th className="p-3">Status</th><th className="p-3">Operational Truth</th></tr>
            </thead>
            <tbody>
              {(readinessQ.data ?? []).map((a) => (
                <tr key={a.channel} className="border-b border-line/60">
                  <td className="p-3 font-mono">{a.channel}</td>
                  <td className="p-3">{a.category}</td>
                  <td className="p-3"><StatusBadge status={a.status} /></td>
                  <td className="p-3 text-ink-muted">{a.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}
