import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { NetworkError } from './api/client';
import App from './App';
import './index.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: true,
      retry: (failureCount, error) => {
        // Don't retry network errors (backend down)
        if (error instanceof NetworkError) return false;
        return failureCount < 1;
      },
      // Pause polling when queries are in error state; hooks override with their own interval
      refetchInterval: (query) => {
        if (query.state.status === 'error') return false;
        return false;
      },
    },
  },
});

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter basename="/dashboard">
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
