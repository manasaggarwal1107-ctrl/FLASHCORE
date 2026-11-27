import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Barcode, CreditCard, PauseCircle, Plus, Printer, Receipt, Trash2, WifiOff } from 'lucide-react';

import { StatusBadge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { FormField, Input, Select } from '@/components/ui/Field';
import { PageHeader } from '@/components/ui/PageHeader';
import { Panel, PanelBody, PanelHeader } from '@/components/ui/Panel';
import { formatMoney } from '@/lib/money';
import { listCatalogProducts, listCustomers } from '@/services/api/commerceApi';
import { expansionApi } from '@/services/api/expansionApi';

function formatPaise(minor: number): string {
  return formatMoney((minor / 100).toFixed(2), 'INR', { locale: 'en-IN' });
}

interface CartLine {
  productId: number;
  sku: string;
  name: string;
  priceMinor: number;
  taxRateBps: number;
  quantity: number;
  itemDiscountInr: string;
}

interface OfflineQueuedOrder {
  offline_tx_id: string;
  payload: Record<string, unknown>;
  createdAt: string;
  totalDisplay: string;
}

const OFFLINE_QUEUE_KEY = 'flashcore.pos.offlineQueue';

function loadOfflineQueue(): OfflineQueuedOrder[] {
  try {
    const raw = window.localStorage.getItem(OFFLINE_QUEUE_KEY);
    return raw ? (JSON.parse(raw) as OfflineQueuedOrder[]) : [];
  } catch {
    return [];
  }
}

export function PosPage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState('');
  const [barcodeInput, setBarcodeInput] = useState('');
  const [locationId, setLocationId] = useState<string>('');
  const [customerId, setCustomerId] = useState<string>('');
  const [couponCode, setCouponCode] = useState('');
  const [couponDiscountMinor, setCouponDiscountMinor] = useState(0);
  const [couponMessage, setCouponMessage] = useState<string | null>(null);
  const [campaignId, setCampaignId] = useState('');
  const [billDiscountInr, setBillDiscountInr] = useState('0');
  const [openingCashInr, setOpeningCashInr] = useState('1000');
  const [countedCashInr, setCountedCashInr] = useState('');
  const [cart, setCart] = useState<CartLine[]>([]);
  const [payMethod, setPayMethod] = useState<'cash' | 'upi' | 'card' | 'bank_transfer' | 'store_credit'>('upi');
  const [utrRef, setUtrRef] = useState('');
  const [splitCashInr, setSplitCashInr] = useState('');
  const [receiptOut, setReceiptOut] = useState<Record<string, unknown> | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [offlineQueue, setOfflineQueue] = useState<OfflineQueuedOrder[]>(loadOfflineQueue);

  const warehousesQ = useQuery({ queryKey: ['pos.warehouses'], queryFn: expansionApi.listWarehouses });
  const productsQ = useQuery({ queryKey: ['pos.products', search], queryFn: () => listCatalogProducts({ search: search || undefined, status: 'active' }) });
  const customersQ = useQuery({ queryKey: ['pos.customers'], queryFn: () => listCustomers({}) });
  const shiftsQ = useQuery({ queryKey: ['pos.shifts'], queryFn: expansionApi.listShifts });
  const heldQ = useQuery({ queryKey: ['pos.held'], queryFn: expansionApi.listHeldBills });
  const campaignsQ = useQuery({ queryKey: ['pos.campaigns'], queryFn: expansionApi.listCampaigns });

  const openShift = shiftsQ.data?.find((s) => s.status === 'OPEN');
  const activeLocId = Number(locationId || openShift?.locationId || warehousesQ.data?.[0]?.id || 0);

  const addProductToCart = (p: { id: string; sku: string; name: string; priceMinor: number; taxRateBps: number }) => {
    const pid = Number(p.id);
    setCart((prev) => {
      const existing = prev.find((l) => l.productId === pid);
      if (existing) return prev.map((l) => (l.productId === pid ? { ...l, quantity: l.quantity + 1 } : l));
      return [...prev, { productId: pid, sku: p.sku, name: p.name, priceMinor: p.priceMinor, taxRateBps: p.taxRateBps, quantity: 1, itemDiscountInr: '0' }];
    });
  };

  const handleBarcodeScan = () => {
    const term = barcodeInput.trim().toLowerCase();
    if (!term) return;
    const match = productsQ.data?.items.find((p) => p.sku.toLowerCase() === term || (p.barcode && p.barcode.toLowerCase() === term));
    if (match) {
      addProductToCart(match);
      setBarcodeInput('');
      setErrorMsg(null);
    } else {
      setErrorMsg(`No active SKU or barcode matched "${barcodeInput}".`);
    }
  };

  const totals = useMemo(() => {
    let sub = 0;
    let itemDisc = 0;
    let tax = 0;
    for (const l of cart) {
      const lineGross = l.priceMinor * l.quantity;
      const disc = Math.round((Number(l.itemDiscountInr) || 0) * 100);
      const taxable = Math.max(0, lineGross - disc);
      sub += lineGross;
      itemDisc += disc;
      tax += Math.round((taxable * l.taxRateBps) / 10000);
    }
    const billDisc = Math.round((Number(billDiscountInr) || 0) * 100);
    const total = Math.max(0, sub + tax - itemDisc - billDisc - couponDiscountMinor);
    return { sub, itemDisc, tax, billDisc, total };
  }, [cart, billDiscountInr, couponDiscountMinor]);

  const openShiftMut = useMutation({
    mutationFn: () => expansionApi.openShift({ location_id: activeLocId, opening_cash_minor: Math.round((Number(openingCashInr) || 0) * 100) }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['pos.shifts'] }),
    onError: (e: Error) => setErrorMsg(e.message),
  });

  const closeShiftMut = useMutation({
    mutationFn: () => {
      if (!openShift) throw new Error('No open shift.');
      return expansionApi.closeShift(openShift.id, Math.round((Number(countedCashInr) || 0) * 100));
    },
    onSuccess: () => {
      setCountedCashInr('');
      void qc.invalidateQueries({ queryKey: ['pos.shifts'] });
    },
    onError: (e: Error) => setErrorMsg(e.message),
  });

  const holdMut = useMutation({
    mutationFn: () =>
      expansionApi.holdBill({
        location_id: activeLocId,
        label: `Counter-${new Date().toLocaleTimeString()}`,
        customer_id: customerId ? Number(customerId) : null,
        coupon_code: couponCode || null,
        discount_minor: totals.billDisc,
        items: cart.map((c) => ({ product_id: c.productId, quantity: c.quantity, item_discount_minor: Math.round((Number(c.itemDiscountInr) || 0) * 100) })),
      }),
    onSuccess: () => {
      setCart([]);
      void qc.invalidateQueries({ queryKey: ['pos.held'] });
    },
    onError: (e: Error) => setErrorMsg(e.message),
  });

  const checkoutMut = useMutation({
    mutationFn: async () => {
      if (!activeLocId || cart.length === 0) throw new Error('Select a store location and add items.');
      const cashMinor = Math.round((Number(splitCashInr) || 0) * 100);
      const payments =
        cashMinor > 0 && cashMinor < totals.total && payMethod !== 'cash'
          ? [
              { method: 'cash', amount_minor: cashMinor },
              { method: payMethod, amount_minor: totals.total - cashMinor, reference_utr: utrRef || null },
            ]
          : [{ method: payMethod, amount_minor: totals.total, reference_utr: utrRef || null }];

      const payload = {
        location_id: activeLocId,
        customer_id: customerId ? Number(customerId) : null,
        shift_id: openShift ? Number(openShift.id) : null,
        campaign_id: campaignId ? Number(campaignId) : null,
        coupon_code: couponCode || null,
        bill_discount_minor: totals.billDisc,
        offline_tx_id: `pos-${Date.now()}`,
        items: cart.map((c) => ({ product_id: c.productId, quantity: c.quantity, item_discount_minor: Math.round((Number(c.itemDiscountInr) || 0) * 100) })),
        payments,
      };
      try {
        return await expansionApi.posCheckout(payload);
      } catch (err) {
        if (!navigator.onLine) {
          const queued: OfflineQueuedOrder = {
            offline_tx_id: String(payload.offline_tx_id),
            payload,
            createdAt: new Date().toISOString(),
            totalDisplay: formatPaise(totals.total),
          };
          const next = [queued, ...offlineQueue];
          setOfflineQueue(next);
          window.localStorage.setItem(OFFLINE_QUEUE_KEY, JSON.stringify(next));
          throw new Error('Offline mode: transaction saved to local POS queue for idempotent sync.');
        }
        throw err;
      }
    },
    onSuccess: (data) => {
      setErrorMsg(null);
      setReceiptOut(data);
      setCart([]);
      setCouponCode('');
      setCouponDiscountMinor(0);
      setSplitCashInr('');
      setUtrRef('');
      void qc.invalidateQueries({ queryKey: ['pos.shifts'] });
      void qc.invalidateQueries({ queryKey: ['pos.products'] });
    },
    onError: (e: Error) => setErrorMsg(e.message),
  });

  const syncOfflineQueue = async () => {
    const remaining: OfflineQueuedOrder[] = [];
    for (const q of offlineQueue) {
      try {
        await expansionApi.posCheckout(q.payload);
      } catch {
        remaining.push(q);
      }
    }
    setOfflineQueue(remaining);
    window.localStorage.setItem(OFFLINE_QUEUE_KEY, JSON.stringify(remaining));
  };

  return (
    <div className="space-y-4">
      <PageHeader
        title="Retail POS & Billing"
        description="Rapid GST billing, split tenders (Cash/UPI/Card), cashier shifts, hold & resume, and offline queue sync."
        actions={
          offlineQueue.length > 0 ? (
            <Button size="sm" variant="secondary" icon={<WifiOff className="h-3.5 w-3.5" />} onClick={() => void syncOfflineQueue()}>
              Sync {offlineQueue.length} queued bill(s)
            </Button>
          ) : null
        }
      />

      {errorMsg && <div role="alert" className="rounded border border-danger/40 bg-danger/10 px-3 py-2 text-xs text-danger">{errorMsg}</div>}

      {/* Shift & Store Bar */}
      <Panel>
        <PanelBody className="flex flex-wrap items-end gap-3">
          <FormField label="Store / Branch">
            {(p) => (
              <Select {...p} value={String(activeLocId)} onChange={(e) => setLocationId(e.target.value)}>
                {(warehousesQ.data ?? []).map((w) => (
                  <option key={w.id} value={w.id}>{w.name} ({w.locationType})</option>
                ))}
              </Select>
            )}
          </FormField>
          {openShift ? (
            <div className="flex flex-wrap items-end gap-2">
              <div className="text-xs text-ink-muted">
                Shift Open · Expected Cash <span className="num font-semibold text-ink">{formatMoney(openShift.expectedCash, 'INR', { locale: 'en-IN' })}</span>
              </div>
              <Input placeholder="Counted Cash (INR)" value={countedCashInr} onChange={(e) => setCountedCashInr(e.target.value)} className="w-40" />
              <Button size="sm" onClick={() => closeShiftMut.mutate()} loading={closeShiftMut.isPending}>Close Shift</Button>
            </div>
          ) : (
            <div className="flex items-end gap-2">
              <FormField label="Opening Cash (INR)">
                {(p) => <Input {...p} value={openingCashInr} onChange={(e) => setOpeningCashInr(e.target.value)} className="w-32" />}
              </FormField>
              <Button size="sm" variant="primary" onClick={() => openShiftMut.mutate()} loading={openShiftMut.isPending}>Open Cashier Shift</Button>
            </div>
          )}
        </PanelBody>
      </Panel>

      <div className="grid gap-4 lg:grid-cols-12">
        {/* Left: Product & Barcode Scanner */}
        <div className="space-y-4 lg:col-span-7">
          <Panel>
            <PanelHeader title="Catalogue & Barcode Entry" />
            <PanelBody className="space-y-3">
              <div className="flex gap-2">
                <Input
                  aria-label="Scan barcode or SKU"
                  placeholder="Scan barcode / exact SKU + Enter..."
                  value={barcodeInput}
                  onChange={(e) => setBarcodeInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') handleBarcodeScan(); }}
                />
                <Button icon={<Barcode className="h-3.5 w-3.5" />} onClick={handleBarcodeScan}>Scan</Button>
              </div>
              <Input aria-label="Search products" placeholder="Filter by product name, SKU, or category..." value={search} onChange={(e) => setSearch(e.target.value)} />
              <div className="grid max-h-80 gap-2 overflow-y-auto sm:grid-cols-2">
                {(productsQ.data?.items ?? []).map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => addProductToCart(p)}
                    className="flex items-center justify-between rounded border border-line bg-surface-raised p-2.5 text-left transition-colors hover:border-accent"
                  >
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium text-ink">{p.name}</div>
                      <div className="text-2xs text-ink-faint">{p.sku} · Stock: {p.inventory?.available ?? 0}</div>
                    </div>
                    <div className="ml-2 shrink-0 text-right">
                      <div className="num text-xs font-semibold text-accent">{formatPaise(p.priceMinor)}</div>
                      <Plus className="ml-auto mt-0.5 h-3.5 w-3.5 text-ink-muted" />
                    </div>
                  </button>
                ))}
              </div>
            </PanelBody>
          </Panel>

          {(heldQ.data?.length ?? 0) > 0 && (
            <Panel>
              <PanelHeader title="Held Bills" badge={<StatusBadge status="PENDING" />} />
              <PanelBody className="flex flex-wrap gap-2">
                {heldQ.data?.map((hb) => (
                  <Button
                    key={hb.id}
                    size="sm"
                    onClick={() => {
                      const restored: CartLine[] = hb.items.map((it) => {
                        const prod = productsQ.data?.items.find((x) => Number(x.id) === it.product_id);
                        return {
                          productId: it.product_id,
                          sku: prod?.sku ?? `SKU-${it.product_id}`,
                          name: prod?.name ?? `Product #${it.product_id}`,
                          priceMinor: prod?.priceMinor ?? 0,
                          taxRateBps: prod?.taxRateBps ?? 0,
                          quantity: it.quantity,
                          itemDiscountInr: '0',
                        };
                      });
                      setCart(restored);
                      if (hb.customerId) setCustomerId(String(hb.customerId));
                    }}
                  >
                    Resume: {hb.label} ({hb.items.length} items)
                  </Button>
                ))}
              </PanelBody>
            </Panel>
          )}
        </div>

        {/* Right: Active Cart & Split Tender */}
        <div className="space-y-4 lg:col-span-5">
          <Panel>
            <PanelHeader
              title="Current Bill"
              actions={
                <Button size="sm" disabled={cart.length === 0} icon={<PauseCircle className="h-3.5 w-3.5" />} onClick={() => holdMut.mutate()}>
                  Hold
                </Button>
              }
            />
            <PanelBody className="space-y-3">
              {cart.length === 0 ? (
                <p className="py-6 text-center text-xs text-ink-faint">Add or scan products to start billing.</p>
              ) : (
                <div className="space-y-2">
                  {cart.map((l) => (
                    <div key={l.productId} className="flex items-center justify-between gap-2 border-b border-line pb-2 text-xs">
                      <div className="min-w-0 flex-1">
                        <div className="truncate font-medium text-ink">{l.name}</div>
                        <div className="text-2xs text-ink-faint">{formatPaise(l.priceMinor)} × {l.quantity}</div>
                      </div>
                      <Input
                        type="number"
                        min={1}
                        value={String(l.quantity)}
                        onChange={(e) => setCart((prev) => prev.map((x) => x.productId === l.productId ? { ...x, quantity: Math.max(1, Number(e.target.value) || 1) } : x))}
                        className="h-7 w-16 text-center"
                      />
                      <Button size="sm" variant="ghost" onClick={() => setCart((prev) => prev.filter((x) => x.productId !== l.productId))}>
                        <Trash2 className="h-3.5 w-3.5 text-danger" />
                      </Button>
                    </div>
                  ))}
                </div>
              )}

              <div className="grid gap-2 sm:grid-cols-2">
                <Select aria-label="Customer" value={customerId} onChange={(e) => setCustomerId(e.target.value)}>
                  <option value="">Walk-in Customer</option>
                  {(customersQ.data?.items ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </Select>
                <Select aria-label="Surge Campaign" value={campaignId} onChange={(e) => setCampaignId(e.target.value)}>
                  <option value="">No Campaign</option>
                  {(campaignsQ.data ?? []).filter((c) => c.status === 'ACTIVE').map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </Select>
              </div>

              <div className="flex gap-2">
                <Input placeholder="Coupon Code" value={couponCode} onChange={(e) => setCouponCode(e.target.value.toUpperCase())} />
                <Button
                  size="sm"
                  onClick={() => {
                    void expansionApi.validateCoupon({ code: couponCode, subtotal_minor: totals.sub, customer_id: customerId ? Number(customerId) : null }).then((r) => {
                      setCouponDiscountMinor(r.valid ? r.discountMinor : 0);
                      setCouponMessage(r.valid ? `Applied -₹${r.discount}` : r.reason || 'Invalid coupon');
                    });
                  }}
                >
                  Apply
                </Button>
              </div>
              {couponMessage && <div className="text-2xs text-ink-muted">{couponMessage}</div>}

              <div className="space-y-1 rounded border border-line bg-surface-raised p-2.5 text-xs">
                <div className="flex justify-between"><span className="text-ink-muted">Subtotal</span><span className="num">{formatPaise(totals.sub)}</span></div>
                <div className="flex justify-between"><span className="text-ink-muted">GST (CGST+SGST / IGST)</span><span className="num">{formatPaise(totals.tax)}</span></div>
                <div className="flex justify-between items-center">
                  <span className="text-ink-muted">Bill Discount (INR)</span>
                  <Input value={billDiscountInr} onChange={(e) => setBillDiscountInr(e.target.value)} className="h-7 w-20 text-right" />
                </div>
                <div className="flex justify-between border-t border-line pt-1 text-sm font-semibold text-ink">
                  <span>Grand Total</span>
                  <span className="num text-accent">{formatPaise(totals.total)}</span>
                </div>
              </div>

              <div className="grid gap-2 sm:grid-cols-2">
                <Select aria-label="Primary tender" value={payMethod} onChange={(e) => setPayMethod(e.target.value as typeof payMethod)}>
                  <option value="upi">UPI</option>
                  <option value="cash">Cash</option>
                  <option value="card">Card</option>
                  <option value="bank_transfer">Bank Transfer</option>
                  <option value="store_credit">Store Credit</option>
                </Select>
                <Input placeholder="UTR / Txn Ref (optional)" value={utrRef} onChange={(e) => setUtrRef(e.target.value)} />
              </div>
              {payMethod !== 'cash' && (
                <Input placeholder="Optional Cash Split Part (INR)" value={splitCashInr} onChange={(e) => setSplitCashInr(e.target.value)} />
              )}

              <Button
                variant="primary"
                className="w-full"
                icon={<CreditCard className="h-4 w-4" />}
                disabled={cart.length === 0}
                loading={checkoutMut.isPending}
                onClick={() => checkoutMut.mutate()}
              >
                Complete POS Sale ({formatPaise(totals.total)})
              </Button>
            </PanelBody>
          </Panel>

          {receiptOut && (
            <Panel>
              <PanelHeader title="POS Tax Invoice Receipt" badge={<Receipt className="h-4 w-4 text-success" />} />
              <PanelBody className="space-y-1 text-xs">
                <div>Order: <span className="font-mono font-semibold">{String(receiptOut.orderNumber ?? receiptOut.order_number)}</span></div>
                <div>Total: <span className="num font-semibold">₹{String(receiptOut.total)}</span></div>
                {Boolean((receiptOut.invoice as { id?: string } | undefined)?.id) && (
                  <a
                    href={`/api/v1/invoices/${(receiptOut.invoice as { id: string }).id}/print`}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-2 inline-flex items-center gap-1.5 text-accent underline"
                  >
                    <Printer className="h-3.5 w-3.5" /> Open Printable Tax Invoice
                  </a>
                )}
              </PanelBody>
            </Panel>
          )}
        </div>
      </div>
    </div>
  );
}
