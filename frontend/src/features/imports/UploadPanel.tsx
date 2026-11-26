import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Info } from 'lucide-react';
import { FormField, Input } from '@/components/ui/Field';
import { Panel, PanelBody, PanelHeader } from '@/components/ui/Panel';
import { FormFooter } from '@/features/shared/FormFooter';
import { useEndpointMutation } from '@/hooks/useEndpointMutation';
import { endpoints } from '@/services/api/endpoints';
import { importSchema } from './importSchema';
import type { ImportFormValues } from './importSchema';

/** Builds the multipart payload. ADAPTER POINT: field names must match API_CONTRACT.md. */
export function buildImportFormData(values: ImportFormValues): FormData {
  const fd = new FormData();
  fd.append('file', values.file);
  fd.append('datasetSource', values.datasetSource);
  if (values.provenance) fd.append('provenance', values.provenance);
  return fd;
}

export function UploadPanel() {
  const mutation = useEndpointMutation<FormData>(endpoints.imports.upload, { invalidatePrefixes: ['imports.list'] });
  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors },
  } = useForm<ImportFormValues>({ resolver: zodResolver(importSchema) });

  return (
    <Panel>
      <PanelHeader title="Upload CSV" description="Import records from a CSV file." />
      <PanelBody>
        <div className="mb-4 flex items-start gap-2 rounded border border-line bg-surface-raised px-3 py-2 text-xs text-ink-muted">
          <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent" aria-hidden />
          <p>
            Uploaded datasets are recorded as <strong className="text-ink">user-supplied</strong>. The platform does not verify that a dataset is authentic; the source and provenance below
            are statements made by the uploader. Imported records stay labelled “Imported”.
          </p>
        </div>
        <form noValidate onSubmit={handleSubmit((values) => mutation.mutate(buildImportFormData(values)))} className="max-w-2xl space-y-4">
          <FormField label="CSV file" error={errors.file?.message as string | undefined}>
            {(p) => (
              <Input
                {...p}
                type="file"
                accept=".csv,text/csv"
                className="h-auto py-1.5 file:mr-3 file:rounded file:border-0 file:bg-surface-overlay file:px-2.5 file:py-1 file:text-xs file:text-ink"
                onChange={(e) => setValue('file', e.target.files?.[0] as File, { shouldValidate: true })}
              />
            )}
          </FormField>
          <FormField label="Dataset source" error={errors.datasetSource?.message} hint="e.g. “Warehouse export, Nov 2026”">
            {(p) => <Input {...p} {...register('datasetSource')} />}
          </FormField>
          <FormField label="Provenance notes (optional)" error={errors.provenance?.message} hint="Who produced it, how, and any known caveats">
            {(p) => <Input {...p} {...register('provenance')} />}
          </FormField>
          <FormFooter
            live={mutation.live}
            capability={endpoints.imports.upload.label}
            submitting={mutation.isPending}
            error={mutation.error}
            success={mutation.isSuccess}
            submitLabel="Upload and import"
          />
        </form>
      </PanelBody>
    </Panel>
  );
}
