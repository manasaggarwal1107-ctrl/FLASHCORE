import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { ArrowRight, LockKeyhole } from 'lucide-react';

import { Button } from '@/components/ui/Button';
import { FormField, Input } from '@/components/ui/Field';
import { useAuth } from '@/hooks/useAuth';
import { loginSchema } from './authSchema';
import type { LoginFormValues } from './authSchema';

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: '',
      password: '',
    },
  });

  const onSubmit = async (values: LoginFormValues) => {
    setServerError(null);

    try {
      await login(values);
      navigate('/overview', { replace: true });
    } catch (cause) {
      setServerError(
        cause instanceof Error
          ? cause.message
          : 'Unable to sign in. Please try again.',
      );
    }
  };

  return (
    <main className="flex min-h-full items-center justify-center bg-canvas px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-lg border border-accent/30 bg-accent/10 text-accent">
            <LockKeyhole className="h-6 w-6" aria-hidden />
          </div>

          <div className="text-2xl font-bold tracking-[0.18em] text-ink">
            FLASHCORE
          </div>
          <p className="mt-2 text-sm text-ink-muted">
            Retail intelligence and simulation platform
          </p>
        </div>

        <section className="panel overflow-hidden">
          <div className="border-b border-line px-6 py-5">
            <p className="eyebrow mb-2">Welcome back</p>
            <h1 className="text-xl font-semibold text-ink">
              Sign in to FLASHCORE
            </h1>
            <p className="mt-1 text-sm text-ink-muted">
              Enter your account credentials to continue.
            </p>
          </div>

          <div className="p-6">
            <form
              noValidate
              className="space-y-4"
              onSubmit={handleSubmit(onSubmit)}
            >
              <FormField
                label="Email address"
                error={errors.email?.message}
              >
                {(props) => (
                  <Input
                    {...props}
                    {...register('email')}
                    type="email"
                    autoComplete="email"
                    placeholder="you@example.com"
                    autoFocus
                  />
                )}
              </FormField>

              <FormField
                label="Password"
                error={errors.password?.message}
              >
                {(props) => (
                  <Input
                    {...props}
                    {...register('password')}
                    type="password"
                    autoComplete="current-password"
                    placeholder="Enter your password"
                  />
                )}
              </FormField>

              {serverError && (
                <div
                  role="alert"
                  className="rounded border border-danger/30 bg-danger/10 px-3 py-2.5 text-sm text-danger"
                >
                  {serverError}
                </div>
              )}

              <Button
                type="submit"
                variant="primary"
                size="md"
                loading={isSubmitting}
                className="w-full"
              >
                Sign in
                <ArrowRight className="h-4 w-4" aria-hidden />
              </Button>
            </form>

            <div className="mt-6 border-t border-line pt-5 text-center">
              <p className="text-sm text-ink-muted">
                Don't have an account?{' '}
                <Link
                  to="/signup"
                  className="font-medium text-accent hover:text-accent-strong"
                >
                  Create account
                </Link>
              </p>
            </div>
          </div>
        </section>

        <p className="mt-5 text-center text-xs text-ink-faint">
          Secure authentication · FLASHCORE
        </p>
      </div>
    </main>
  );
}
