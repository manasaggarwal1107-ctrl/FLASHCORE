import { OriginBadge, StatusBadge } from '@/components/ui/Badge';
import { Panel, PanelBody, PanelHeader } from '@/components/ui/Panel';
import { DetailList } from '@/features/shared/DetailList';
import { DetailPage } from '@/features/shared/DetailPage';
import { formatDateTime } from '@/lib/format';
import { endpoints } from '@/services/api/endpoints';
import type { Transaction } from '@/types/api';

export function TransactionDetailPage() {
  return (
    <DetailPage<Transaction>
      endpoint={endpoints.transactions.get}
      backTo="/transactions"
      backLabel="Transaction monitor"
      title={(t, id) => `Purchase attempt ${t?.purchaseAttemptId ?? id}`}
    >
      {(t) => (
        <Panel>
          <PanelHeader
            title="Attempt details"
            badge={<StatusBadge status={t.status} />}
            actions={<OriginBadge origin={t.origin} />}
          />
          <PanelBody>
            <DetailList
              items={[
                { label: 'Purchase attempt ID', value: t.purchaseAttemptId ?? t.id, mono: true },
                { label: 'Timestamp', value: formatDateTime(t.occurredAt) },
                { label: 'Failure reason', value: t.failureReason },
                { label: 'Source', value: 'Simulation' },
              ]}
            />
          </PanelBody>
        </Panel>
      )}
    </DetailPage>
  );
}
