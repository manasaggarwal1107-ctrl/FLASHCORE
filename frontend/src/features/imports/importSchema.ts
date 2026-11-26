import { z } from 'zod';

/** ASSUMPTION: client-side size guard only; confirm the server's real limit in API_CONTRACT.md. */
export const MAX_IMPORT_BYTES = 10 * 1024 * 1024;

export const importSchema = z.object({
  file: z
    .custom<File>((v) => typeof File !== 'undefined' && v instanceof File, 'Choose a CSV file')
    .refine((f) => /\.csv$/i.test(f.name), 'File must have a .csv extension')
    .refine((f) => f.size > 0, 'File is empty')
    .refine((f) => f.size <= MAX_IMPORT_BYTES, `File must be ${MAX_IMPORT_BYTES / 1024 / 1024} MB or smaller`),
  datasetSource: z.string().trim().min(2, 'Describe where this dataset came from').max(300),
  provenance: z.string().trim().max(1000).optional().or(z.literal('')),
});

export type ImportFormValues = z.infer<typeof importSchema>;
