import { z } from 'zod';

export const tokenSchema = z.object({
  token: z
    .string()
    .trim()
    .min(1, 'Enter a token')
    .regex(/^\S+$/, 'Token must not contain spaces')
    .max(4096, 'Token is too long'),
});

export type TokenFormValues = z.infer<typeof tokenSchema>;
