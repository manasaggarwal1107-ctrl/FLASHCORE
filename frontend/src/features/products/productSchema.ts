import { z } from 'zod';

/** Decimal string with at most 2 fraction digits, e.g. "19.99". Never parsed as a float. */
export const decimalString = z
  .string()
  .trim()
  .regex(/^\d+(\.\d{1,2})?$/, 'Enter a positive amount with up to 2 decimals');

export const productSchema = z.object({
  name: z.string().trim().min(1, 'Name is required').max(200, 'Name is too long'),
  sku: z
    .string()
    .trim()
    .max(64, 'SKU is too long')
    .regex(/^[A-Za-z0-9._-]*$/, 'Use letters, numbers, dot, dash or underscore')
    .optional()
    .or(z.literal('')),
  category: z.string().trim().max(100).optional().or(z.literal('')),
  status: z.enum(['active', 'draft', 'archived']),
  price: decimalString,
  currency: z
    .string()
    .trim()
    .toUpperCase()
    .regex(/^[A-Z]{3}$/, 'Use a 3-letter ISO currency code'),
});

export type ProductFormValues = z.infer<typeof productSchema>;
