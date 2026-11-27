import type { PaymentOrder } from '@/types/api';

export interface RazorpaySuccessResponse {
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
}

export interface RazorpayInstance {
  open: () => void;
  on: (event: string, cb: (payload: { error?: { description?: string; reason?: string; code?: string } }) => void) => void;
}

export interface RazorpayConstructor {
  new (options: Record<string, unknown>): RazorpayInstance;
}

declare global {
  interface Window {
    Razorpay?: RazorpayConstructor;
  }
}

const RAZORPAY_SCRIPT_SRC = 'https://checkout.razorpay.com/v1/checkout.js';
let scriptPromise: Promise<RazorpayConstructor> | null = null;

export function loadRazorpayCheckoutScript(): Promise<RazorpayConstructor> {
  if (typeof window !== 'undefined' && window.Razorpay) {
    return Promise.resolve(window.Razorpay);
  }
  if (scriptPromise) return scriptPromise;

  scriptPromise = new Promise<RazorpayConstructor>((resolve, reject) => {
    if (typeof document === 'undefined') {
      reject(new Error('Razorpay Checkout requires a browser environment.'));
      return;
    }

    const existing = document.querySelector<HTMLScriptElement>(`script[src="${RAZORPAY_SCRIPT_SRC}"]`);
    if (existing) {
      existing.addEventListener('load', () => {
        if (window.Razorpay) resolve(window.Razorpay);
        else reject(new Error('Razorpay Checkout SDK loaded without window.Razorpay.'));
      });
      existing.addEventListener('error', () => {
        scriptPromise = null;
        reject(new Error('Failed to load Razorpay Checkout script.'));
      });
      return;
    }

    const script = document.createElement('script');
    script.src = RAZORPAY_SCRIPT_SRC;
    script.async = true;
    script.onload = () => {
      if (window.Razorpay) {
        resolve(window.Razorpay);
      } else {
        scriptPromise = null;
        reject(new Error('Razorpay Checkout SDK did not register window.Razorpay.'));
      }
    };
    script.onerror = () => {
      scriptPromise = null;
      reject(new Error('Unable to load Razorpay Standard Checkout SDK.'));
    };
    document.head.appendChild(script);
  });

  return scriptPromise;
}

export function resetRazorpayLoaderForTest() {
  scriptPromise = null;
}

export async function openRazorpayStandardCheckout(
  paymentOrder: PaymentOrder,
  options?: { orderReference?: string; description?: string },
): Promise<RazorpaySuccessResponse> {
  if (paymentOrder.mode !== 'test' || !paymentOrder.keyId.startsWith('rzp_test_')) {
    throw new Error('Only Razorpay Test Mode is permitted in this release.');
  }

  const Razorpay = await loadRazorpayCheckoutScript();

  return new Promise<RazorpaySuccessResponse>((resolve, reject) => {
    let settled = false;
    const settleResolve = (val: RazorpaySuccessResponse) => {
      if (settled) return;
      settled = true;
      resolve(val);
    };
    const settleReject = (err: Error) => {
      if (settled) return;
      settled = true;
      reject(err);
    };

    const rzp = new Razorpay({
      key: paymentOrder.keyId,
      amount: paymentOrder.amountMinor,
      currency: paymentOrder.currency,
      name: 'FLASHCORE',
      description: options?.description ?? `Order ${options?.orderReference ?? paymentOrder.receipt}`,
      order_id: paymentOrder.providerOrderId,
      prefill: {
        name: paymentOrder.prefill?.name ?? undefined,
        email: paymentOrder.prefill?.email ?? undefined,
        contact: paymentOrder.prefill?.contact ?? undefined,
      },
      theme: { color: '#22d3ee' },
      handler: (response: RazorpaySuccessResponse) => {
        settleResolve(response);
      },
      modal: {
        ondismiss: () => {
          settleReject(new Error('Checkout modal closed before payment completion.'));
        },
      },
    });

    rzp.on('payment.failed', (evt) => {
      const desc = evt?.error?.description || evt?.error?.reason || 'Payment failed in gateway.';
      settleReject(new Error(desc));
    });

    rzp.open();
  });
}
