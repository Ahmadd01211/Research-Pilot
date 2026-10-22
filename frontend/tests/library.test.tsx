import { afterEach, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppRoutes } from '../src/app/router';

const id = '11111111-1111-4111-8111-111111111111';
const paper = { id: 'paper-id', project_id: id, filename: 'Evidence.pdf', byte_size: 1000, status: 'stored', created_at: '2026-10-19T00:00:00Z' };
afterEach(() => vi.unstubAllGlobals());
function open(archived = false, fail = false) {
  let saved = false;
  const mock = vi.fn((url: string, init?: RequestInit) => {
    if (url === '/api/v1/me') return Promise.resolve(Response.json({ display_name: 'Researcher', email: 'r@example.com' }));
    if (url === '/api/v1/auth/csrf') return Promise.resolve(Response.json({ csrf_token: 'synthetic' }));
    if (init?.method === 'POST') { saved = true; return Promise.resolve(Response.json({ document: paper, duplicate: true })); }
    if (url.includes('/documents')) return Promise.resolve(fail ? Response.json({ detail: 'Unavailable' }, { status: 503 }) : Response.json({ items: saved ? [paper] : [], total: saved ? 1 : 0 }));
    return Promise.resolve(Response.json({ id, title: 'Research focus', archived_at: archived ? '2026-10-19' : null }));
  });
  vi.stubGlobal('fetch', mock);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[`/projects/${id}/library`]}><AppRoutes/></MemoryRouter></QueryClientProvider>);
  return mock;
}
it('uploads raw PDF with CSRF, refreshes the table and explains duplicate reuse', async () => {
  const mock = open(); const ui = userEvent.setup();
  expect(await screen.findByText('Build your evidence library')).toBeVisible();
  const file = new File(['%PDF-1.4'], 'Evidence.pdf', { type: 'application/pdf' });
  await ui.upload(screen.getByLabelText('Choose PDF'), file);
  expect(await screen.findByText(/No duplicate was stored/)).toBeVisible();
  expect(await screen.findByRole('rowheader', { name: 'Evidence.pdf' })).toBeVisible();
  expect(screen.getByRole('link', { name: 'Download Evidence.pdf' })).toHaveAttribute('href', `/api/v1/projects/${id}/documents/paper-id/download`);
  const request = mock.mock.calls.find(([, init]) => init?.method === 'POST');
  expect(request?.[1]?.body).toBe(file);
  expect(request?.[1]?.headers).toEqual({ 'content-type': 'application/pdf', 'x-csrf-token': 'synthetic' });
  expect(screen.getByText(/Eligible papers can then be indexed/)).toBeVisible();
});
it('blocks empty files before a network upload', async () => {
  const mock = open(); const ui = userEvent.setup();
  await screen.findByText('Build your evidence library');
  await ui.upload(screen.getByLabelText('Choose PDF'), new File([], 'Empty.pdf', { type: 'application/pdf' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('nonempty PDF');
  expect(mock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false);
});
it('disables uploads for archived projects', async () => {
  open(true);
  expect(await screen.findByRole('button', { name: 'Upload PDF' })).toBeDisabled();
  expect(screen.getByText(/Existing originals remain available/)).toBeVisible();
});
it('offers a real retry when the library cannot be read', async () => {
  open(false, true);
  expect(await screen.findByRole('button', { name: 'Retry library' })).toBeVisible();
  expect(screen.queryByText('Build your evidence library')).not.toBeInTheDocument();
});
