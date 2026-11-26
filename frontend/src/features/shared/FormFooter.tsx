import { PlugZap } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { describeError } from '@/services/api/errors';

/**
 * Standard form footer. Submit is disabled with an explanation while the endpoint is not
 * connected; server errors are shown verbatim from the API, success is acknowledged explicitly.
 */
export function FormFooter({
  live,
  capability,
  submitting,
  error,
  success,
  submitLabel,
  onCancel,
}: {
  live: boolean;
  capability: string;
  submitting: boolean;
  error: unknown;
  success: boolean;
  submitLabel: string;
  onCancel?: () => void;
}) {
  const apiError = error ? describeError(error) : null;
  return (
    <div className="space-y-3 border-t border-line pt-4">
      {!live && (
        <p className="flex items-start gap-2 rounded border border-warning/30 bg-warning/10 px-3 py-2 text-xs text-warning">
          <PlugZap className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
          <span>
            “{capability}” is not connected yet (awaiting <code className="font-mono">API_CONTRACT.md</code>). The form validates input but cannot be submitted.
          </span>
        </p>
      )}
      {apiError && (
        <p role="alert" className="rounded border border-danger/30 bg-danger/10 px-3 py-2 text-xs text-danger">
          <strong className="font-semibold">{apiError.title}.</strong> {apiError.detail}
        </p>
      )}
      {success && (
        <p role="status" className="rounded border border-success/30 bg-success/10 px-3 py-2 text-xs text-success">
          Saved successfully.
        </p>
      )}
      <div className="flex items-center justify-end gap-2">
        {onCancel && (
          <Button variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
        )}
        <Button type="submit" variant="primary" loading={submitting} disabled={!live}>
          {submitLabel}
        </Button>
      </div>
    </div>
  );
}
