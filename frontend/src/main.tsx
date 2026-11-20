import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { RouterProvider } from 'react-router/dom';
import { FluentProvider } from '@fluentui/react-components';
import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ApiError } from './api/client';
import { AuthProvider } from './auth/AuthContext';
import { handleQueryError } from './auth/session';
import { router } from './router';
import { GlobalStyles } from './theme/GlobalStyles';
import { orionTheme } from './theme/orionTheme';

// staleTime 30s; never retry 4xx (they are rule/permission answers, not glitches).
// Any 401 (session expired / demo reset) logs the user out via handleQueryError (F7).
const queryClient = new QueryClient({
  queryCache: new QueryCache({ onError: handleQueryError }),
  mutationCache: new MutationCache({ onError: handleQueryError }),
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: (count, error) =>
        !(error instanceof ApiError && error.status >= 400 && error.status < 500) && count < 2,
    },
  },
});

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <FluentProvider theme={orionTheme}>
      <GlobalStyles />
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <RouterProvider router={router} />
        </AuthProvider>
      </QueryClientProvider>
    </FluentProvider>
  </StrictMode>,
);
