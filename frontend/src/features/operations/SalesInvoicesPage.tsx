import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Printer } from 'lucide-react';

import { StatusBadge } from '@/components/ui/Badge';
import { Input } from '@/components/ui/Field';
import { PageHeader } from '@/components/ui/PageHeader';
import { Panel, PanelBody, PanelHeader } from '@/components/ui/Panel';
import { StatTile } from '@/components/ui/StatTile';
import { expansionApi } from '@/services/api/expansionApi';

export function SalesInvoicesPage() {
  const [search, setSearch] = useState('');
  const salesQ = useQuery({ queryKey: ['sales.records', search], queryFn: () => expansionApi.listSalesRecords(search || undefined) });
  const pnlQ = useQuery({ queryKey: ['sales.pnl'], queryFn: expansionApi.getSalesPnl });
  const invQ = useQuery({ queryKey: ['sales.invoices'], queryFn: expansionApi.listInvoices });

  const pnl = pnlQ.data as Record<string, unknown> | undefined;

  return (
    <div className="space-y-4">
      <PageHeader title="Sales Records, Invoices & P&L" description="Traceable sales ledger separated from Gross Revenue, GST Taxes, Discounts, Returns, COGS, and Gross Profit." />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <StatTile label="Gross Sales" state={pnl ? { kind: 'value', value: `₹${String(pnl.grossSales ?? '0.00')}` } : { kind: 'loading' }} />
        <StatTile label="Discounts" state={pnl ? { kind: 'value', value: `₹${String(pnl.discounts ?? '0.00')}` } : { kind: 'loading' }} />
        <StatTile label="Returns" state={pnl ? { kind: 'value', value: `₹${String(pnl.returnsRefunded ?? '0.00')}` } : { kind: 'loading' }} />
        <StatTile label="Tax Collected" state={pnl ? { kind: 'value', value: `₹${String(pnl.taxCollected ?? '0.00')}` } : { kind: 'loading' }} />
        <StatTile label="Net Sales (Ex Tax)" state={pnl ? { kind: 'value', value: `₹${String(pnl.netSalesExTax ?? '0.00')}` } : { kind: 'loading' }} />
        <StatTile
          label="Gross Profit"
          state={pnl ? (pnl.grossProfit ? { kind: 'value', value: `₹${String(pnl.grossProfit)}` } : { kind: 'unavailable', reason: 'Missing cost on some SKUs' }) : { kind: 'loading' }}
        />
      </div>

      <Panel>
        <PanelHeader title="Sales Transaction Ledger" actions={<Input placeholder="Search order / ref / customer..." value={search} onChange={(e) => setSearch(e.target.value)} className="w-60" />} />
        <PanelBody className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-line text-ink-faint">
                <tr><th className="p-3">Order</th><th className="p-3">Txn Ref</th><th className="p-3">Customer</th><th className="p-3">Gross</th><th className="p-3">Tax</th><th className="p-3">Net</th><th className="p-3">Refund</th></tr>
              </thead>
              <tbody>
                {(salesQ.data?.items ?? []).map((r) => (
                  <tr key={r.id} className="border-b border-line/60">
                    <td className="p-3 font-mono">{r.orderNumber}</td>
                    <td className="p-3 font-mono">{r.transactionRef}</td>
                    <td className="p-3">{r.customerName ?? 'Walk-in'}</td>
                    <td className="p-3 num">₹{r.grossAmount}</td>
                    <td className="p-3 num">₹{r.tax}</td>
                    <td className="p-3 num font-semibold">₹{r.netAmount}</td>
                    <td className="p-3"><StatusBadge status={r.refundStatus} /></td>
                  </tr>
                ))}
                {(salesQ.data?.items.length ?? 0) === 0 && (
                  <tr><td colSpan={7} className="p-6 text-center text-ink-faint">No paid sales records recorded yet.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </PanelBody>
      </Panel>

      <Panel>
        <PanelHeader title="GST Invoices, Bills of Supply & Credit Notes" />
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-line text-ink-faint">
              <tr><th className="p-3">Invoice #</th><th className="p-3">Type</th><th className="p-3">Customer</th><th className="p-3">CGST</th><th className="p-3">SGST</th><th className="p-3">IGST</th><th className="p-3">Total</th><th className="p-3">Print</th></tr>
            </thead>
            <tbody>
              {(invQ.data ?? []).map((i) => (
                <tr key={i.id} className="border-b border-line/60">
                  <td className="p-3 font-mono font-medium">{i.invoiceNumber}</td>
                  <td className="p-3"><StatusBadge status={i.documentType} /></td>
                  <td className="p-3">{i.customerName ?? 'Walk-in'}</td>
                  <td className="p-3 num">₹{i.cgst}</td>
                  <td className="p-3 num">₹{i.sgst}</td>
                  <td className="p-3 num">₹{i.igst}</td>
                  <td className="p-3 num font-semibold">₹{i.total}</td>
                  <td className="p-3">
                    <a href={`/api/v1/invoices/${i.id}/print`} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-accent underline">
                      <Printer className="h-3 w-3" /> Print
                    </a>
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
