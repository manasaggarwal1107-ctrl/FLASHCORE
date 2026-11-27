import { useCallback, useState } from 'react';
import type { ReactNode } from 'react';
import { QueryClientProvider } from '@tanstack/react-query';
import { createQueryClient } from '@/services/api/queryClient';
import { AuthProvider } from '@/app/AuthProvider';
import { ThemeProvider } from '@/components/layout/ThemeProvider';

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(createQueryClient);

  const clearCache = useCallback(() => {
    void client.cancelQueries();
    client.clear();
  }, [client]);

  return (
    <ThemeProvider>
      <QueryClientProvider client={client}>
        <AuthProvider onClearCache={clearCache}>
          {children}
        </AuthProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
