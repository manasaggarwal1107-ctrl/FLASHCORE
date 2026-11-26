import { z } from 'zod';
import { decimalString } from '@/features/products/productSchema';

/** `datetime-local` values look like 2026-11-20T09:30 (no timezone). */
const localDateTime = z.string().min(1, 'Required').refine((v) => !Number.isNaN(new Date(v).getTime()), 'Enter a valid date and time');

export const flashSaleSchema = z
  .object({
    name: z.string().trim().min(1, 'Name is required').max(200),
    productId: z.string().trim().min(1, 'Product reference is required'),
    salePrice: decimalString,
    currency: z
      .string()
      .trim()
      .toUpperCase()
      .regex(/^[A-Z]{3}$/, 'Use a 3-letter ISO currency code'),
    allocated: z.coerce.number({ invalid_type_error: 'Enter a whole number' }).int('Must be a whole number').positive('Must be greater than zero'),
    startsAt: localDateTime,
    endsAt: localDateTime,
  })
  .refine((v) => new Date(v.endsAt).getTime() > new Date(v.startsAt).getTime(), {
    path: ['endsAt'],
    message: 'End must be after start',
  });

export type FlashSaleFormValues = z.infer<typeof flashSaleSchema>;
