import { afterEach, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppRoutes } from '../src/app/router';

const projectId = '11111111-1111-4111-8111-111111111111';
const draftId = '22222222-2222-4222-8222-222222222222';
const referenceId = '33333333-3333-4333-8333-333333333333';
afterEach(() => vi.unstubAllGlobals());

it('inserts a verified reference marker and saves researcher text as the next revision', async () => {
  const draft = { id: draftId, title: 'Review', body: '# Introduction\n', reference_ids: [], revision: 1, created_at: '2026-10-21T00:00:00Z', updated_at: '2026-10-21T00:00:00Z' };
  const mock = vi.fn((url: string, init?: RequestInit) => {
    if (url === '/api/v1/me') return Promise.resolve(Response.json({ display_name: 'Researcher', email: 'r@example.com' }));
    if (url === '/api/v1/auth/csrf') return Promise.resolve(Response.json({ csrf_token: 'synthetic' }));
    if (url.endsWith(`/drafts/${draftId}`) && init?.method === 'PUT') { const saved = JSON.parse(String(init.body)); return Promise.resolve(Response.json({ ...draft, ...saved, revision: 2 })); }
    if (url.endsWith(`/drafts/${draftId}/versions`)) return Promise.resolve(Response.json({ items: [{ ...draft, revision: 1 }], next_before_revision: null }));
    if (url.endsWith(`/drafts/${draftId}`)) return Promise.resolve(Response.json(draft));
    if (url.endsWith('/references')) return Promise.resolve(Response.json({ items: [{ id: referenceId, title: 'Verified paper', authors: ['A. Scholar'], year: 2024, document_id: null }] }));
    return Promise.resolve(Response.json({ id: projectId, title: 'AI adoption', archived_at: null }));
  });
  vi.stubGlobal('fetch', mock);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const router = createMemoryRouter([{ path: '*', element: <AppRoutes/> }], { initialEntries: [`/projects/${projectId}/writing/${draftId}`] });
  render(<QueryClientProvider client={client}><RouterProvider router={router}/></QueryClientProvider>);
  const ui = userEvent.setup();
  await ui.click(await screen.findByRole('button', { name: 'Insert citation' }));
  await ui.click(screen.getByRole('button', { name: 'Save new version' }));
  const call = mock.mock.calls.find(([url, init]) => url.endsWith(`/drafts/${draftId}`) && init?.method === 'PUT');
  const saved = JSON.parse(String(call?.[1]?.body));
  expect(saved).toMatchObject({ expected_revision: 1, title: 'Review' });
  expect(String(saved.body)).toContain(`[@${referenceId}]`);
});
