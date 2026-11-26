import { z } from 'zod';

const emailSchema = z
  .string()
  .trim()
  .toLowerCase()
  .min(5, 'Email must contain at least 5 characters.')
  .max(320, 'Email must not exceed 320 characters.')
  .email('Enter a valid email address.');

export const loginSchema = z.object({
  email: emailSchema,
  password: z
    .string()
    .min(1, 'Enter your password.')
    .max(128, 'Password must not exceed 128 characters.'),
});

export const signupSchema = z
  .object({
    email: emailSchema,
    password: z
      .string()
      .min(12, 'Password must contain at least 12 characters.')
      .max(128, 'Password must not exceed 128 characters.'),
    confirmPassword: z
      .string()
      .min(1, 'Confirm your password.'),
  })
  .refine((values) => values.password === values.confirmPassword, {
    message: 'Passwords do not match.',
    path: ['confirmPassword'],
  });

export type LoginFormValues = z.infer<typeof loginSchema>;
export type SignupFormValues = z.infer<typeof signupSchema>;
