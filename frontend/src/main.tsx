import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { createBrowserRouter, RouterProvider } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppRoutes } from '@/app/router';
import { AppErrorBoundary } from '@/components/shared/app-error-boundary';
import '@/styles/globals.css';

const router = createBrowserRouter([{ path: '*', element: <AppRoutes/> }]);
const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } } });
createRoot(document.getElementById('root')!).render(
  <StrictMode><AppErrorBoundary><QueryClientProvider client={queryClient}><RouterProvider router={router}/></QueryClientProvider></AppErrorBoundary></StrictMode>,
);
