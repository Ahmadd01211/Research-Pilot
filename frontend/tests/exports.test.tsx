import { afterEach, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppRoutes } from '../src/app/router';

const projectId = '11111111-1111-4111-8111-111111111111';
const exportId = '22222222-2222-4222-8222-222222222222';
afterEach(() => vi.unstubAllGlobals());

it('creates a reference CSV snapshot and offers the same saved file in history', async () => {
  let items: unknown[] = [];
  const mock = vi.fn((url: string, init?: RequestInit) => {
    if (url === '/api/v1/me') return Promise.resolve(Response.json({ display_name: 'Researcher', email: 'r@example.com' }));
    if (url === '/api/v1/auth/csrf') return Promise.resolve(Response.json({ csrf_token: 'synthetic' }));
    if (url.endsWith('/drafts')) return Promise.resolve(Response.json({ items: [] }));
    if (url.includes('/exports?offset=')) return Promise.resolve(Response.json({ items, total: items.length }));
    if (url.endsWith('/exports') && init?.method === 'POST') {
      const body = JSON.parse(String(init.body));
      items = [{ id: exportId, filename: 'references.csv', kind: body.kind, byte_size: 128, created_at: '2026-10-21T00:00:00Z' }];
      return Promise.resolve(Response.json(items[0], { status: 201 }));
    }
    return Promise.resolve(Response.json({ id: projectId, title: 'AI adoption', archived_at: null }));
  });
  vi.stubGlobal('fetch', mock);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[`/projects/${projectId}/exports`]}><AppRoutes/></MemoryRouter></QueryClientProvider>);
  expect(await screen.findByRole('option', { name: 'Reference records · Excel' })).toBeInTheDocument();
  expect(screen.getByRole('option', { name: 'Writing draft · Word' })).toBeInTheDocument();
  await userEvent.setup().click(await screen.findByRole('button', { name: 'Create snapshot' }));
  const call = mock.mock.calls.find(([url, init]) => url.endsWith('/exports') && init?.method === 'POST');
  expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({ kind: 'reference_csv', draft_id: null });
  expect((await screen.findAllByRole('link', { name: /Download/ }))[0]).toHaveAttribute('href', `/api/v1/projects/${projectId}/exports/${exportId}/download`);
});

it('sends the selected draft revision for a Word snapshot', async () => {
  const draftId = '33333333-3333-4333-8333-333333333333';
  const mock = vi.fn((url: string, init?: RequestInit) => {
    if (url === '/api/v1/me') return Promise.resolve(Response.json({ display_name: 'Researcher', email: 'r@example.com' }));
    if (url === '/api/v1/auth/csrf') return Promise.resolve(Response.json({ csrf_token: 'synthetic' }));
    if (url.endsWith('/drafts')) return Promise.resolve(Response.json({ items: [{ id: draftId, title: 'Review', revision: 3 }] }));
    if (url.includes('/exports?offset=')) return Promise.resolve(Response.json({ items: [], total: 0 }));
    if (url.endsWith('/exports') && init?.method === 'POST') return Promise.resolve(Response.json({ id: exportId, filename: 'draft.docx', kind: 'draft_docx', byte_size: 128, created_at: '2026-10-21T00:00:00Z' }, { status: 201 }));
    return Promise.resolve(Response.json({ id: projectId, title: 'AI adoption', archived_at: null }));
  });
  vi.stubGlobal('fetch', mock);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[`/projects/${projectId}/exports`]}><AppRoutes/></MemoryRouter></QueryClientProvider>);
  const ui = userEvent.setup();
  await ui.selectOptions(await screen.findByRole('combobox', { name: 'File type' }), 'draft_docx');
  await ui.selectOptions(await screen.findByRole('combobox', { name: 'Draft' }), draftId);
  await ui.click(screen.getByRole('button', { name: 'Create snapshot' }));
  const call = mock.mock.calls.find(([url, init]) => url.endsWith('/exports') && init?.method === 'POST');
  expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({ kind: 'draft_docx', draft_id: draftId, expected_revision: 3 });
});
