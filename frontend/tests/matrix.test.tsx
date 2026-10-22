import { afterEach, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppRoutes } from '../src/app/router';

const projectId = '11111111-1111-4111-8111-111111111111';
const paperId = '22222222-2222-4222-8222-222222222222';
afterEach(() => vi.unstubAllGlobals());

it('saves a user-authored matrix note only with its chosen source and links the result', async () => {
  let rows: unknown[] = [];
  const mock = vi.fn((url: string, init?: RequestInit) => {
    if (url === '/api/v1/me') return Promise.resolve(Response.json({ display_name: 'Researcher', email: 'r@example.com' }));
    if (url === '/api/v1/auth/csrf') return Promise.resolve(Response.json({ csrf_token: 'synthetic' }));
    if (url.endsWith('/matrix/sources?document_id=' + paperId + '&page=1&offset=0&limit=100')) return Promise.resolve(Response.json({ total: 1, items: [{ chunk_id: 'chunk-1', page_number: 1, kind: 'prose', text: 'The authors surveyed firms.', source_sha256: 'abc', reader_version: 'reader-v1', source_metadata: { passage_id: 'passage-1' } }] }));
    if (url.endsWith('/matrix') && init?.method === 'POST') {
      const body = JSON.parse(String(init.body));
      rows = [{ id: 'row-1', document_id: paperId, document_filename: 'Paper.pdf', revision: 1, created_at: '2026-10-21T00:00:00Z', updated_at: '2026-10-21T00:00:00Z', cells: body.cells.map((cell: Record<string, unknown>) => ({ ...cell, source_sha256: 'abc', reader_version: 'reader-v1', page_number: 1, kind: 'prose', source_metadata: { passage_id: 'passage-1' } })) }];
      return Promise.resolve(Response.json(rows[0], { status: 201 }));
    }
    if (url.endsWith('/matrix')) return Promise.resolve(Response.json({ items: rows }));
    if (url.includes('/documents?')) return Promise.resolve(Response.json({ items: [{ id: paperId, filename: 'Paper.pdf', status: 'extracted' }], total: 1 }));
    return Promise.resolve(Response.json({ id: projectId, title: 'AI adoption', archived_at: null }));
  });
  vi.stubGlobal('fetch', mock);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[`/projects/${projectId}/matrix`]}><AppRoutes/></MemoryRouter></QueryClientProvider>);
  const ui = userEvent.setup();
  await ui.click(await screen.findByRole('button', { name: 'Add evidence row' }));
  await ui.selectOptions(screen.getByLabelText('Paper'), paperId);
  await ui.type(screen.getByLabelText('Finding'), 'Adoption varied by firm size.');
  await ui.selectOptions(await screen.findByLabelText('Finding supporting passage'), 'chunk-1');
  await ui.click(screen.getByRole('button', { name: 'Save evidence row' }));
  const call = mock.mock.calls.find(([url, init]) => url.endsWith('/matrix') && init?.method === 'POST');
  expect(JSON.parse(String(call?.[1]?.body))).toEqual({ document_id: paperId, cells: [{ field: 'finding', value: 'Adoption varied by firm size.', chunk_id: 'chunk-1' }] });
  expect(await screen.findByText('Adoption varied by firm size.')).toBeVisible();
  expect(screen.getByRole('link', { name: /PDF p. 1/ })).toHaveAttribute('href', `/projects/${projectId}/library/${paperId}?page=1&source=abc&reader=reader-v1&passage=passage-1`);
});
