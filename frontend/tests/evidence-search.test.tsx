import { afterEach, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppRoutes } from '../src/app/router';

const projectId = '11111111-1111-4111-8111-111111111111';
const paperId = '22222222-2222-4222-8222-222222222222';
afterEach(() => vi.unstubAllGlobals());

function open(enabled: boolean) {
  const mock = vi.fn((url: string, init?: RequestInit) => {
    if (url === '/api/v1/me') return Promise.resolve(Response.json({ display_name: 'Researcher', email: 'r@example.com' }));
    if (url === '/api/v1/auth/csrf') return Promise.resolve(Response.json({ csrf_token: 'synthetic' }));
    if (url.endsWith('/evidence/capabilities')) return Promise.resolve(Response.json({ embedding_enabled: enabled }));
    if (url.endsWith('/evidence/indexes')) return Promise.resolve(Response.json({ items: enabled ? [{ document_id: paperId, state: 'ready', processed_chunks: 2, total_chunks: 2, error_code: null }] : [] }));
    if (url.includes('/documents?')) return Promise.resolve(Response.json({ items: [{ id: paperId, filename: 'Evidence.pdf', status: 'extracted' }], total: 1 }));
    if (url.endsWith('/evidence/search') && init?.method === 'POST') return Promise.resolve(Response.json({ model: 'gemini-embedding-2', index_format: 'gemini2-qa-v1:l2', hits: [{ chunk_id: 'chunk-1', document_id: paperId, source_sha256: 'abc', reader_version: 'reader-v1', page_number: 9, kind: 'prose', source_id: 'passage-2', text: 'Adoption varied by firm size.', source_metadata: { passage_id: 'passage-2' }, distance: 0.2 }] }));
    return Promise.resolve(Response.json({ id: projectId, title: 'AI adoption', archived_at: null }));
  });
  vi.stubGlobal('fetch', mock);
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}><MemoryRouter initialEntries={[`/projects/${projectId}/evidence`]}><AppRoutes/></MemoryRouter></QueryClientProvider>);
  return mock;
}

it('explains unavailable hosted search without offering indexing', async () => {
  open(false);
  expect(await screen.findByText(/Hosted evidence search is not configured yet/)).toBeVisible();
  expect(screen.queryByRole('button', { name: 'Index paper' })).not.toBeInTheDocument();
  expect(await screen.findByRole('button', { name: 'Find evidence' })).toBeDisabled();
});

it('searches only selected indexed papers and links a result to the measured passage', async () => {
  const mock = open(true), ui = userEvent.setup();
  await ui.click(await screen.findByRole('checkbox'));
  await ui.type(screen.getByLabelText('Research question'), 'How did adoption vary?');
  await ui.click(screen.getByRole('button', { name: 'Find evidence' }));
  expect(await screen.findByText('Adoption varied by firm size.')).toBeVisible();
  const call = mock.mock.calls.find(([url, init]) => url.endsWith('/evidence/search') && init?.method === 'POST');
  expect(JSON.parse(String(call?.[1]?.body))).toEqual({ question: 'How did adoption vary?', document_ids: [paperId] });
  expect(screen.getByRole('link', { name: /Check in original PDF/ })).toHaveAttribute('href', `/projects/${projectId}/library/${paperId}?page=9&source=abc&reader=reader-v1&passage=passage-2`);
});
