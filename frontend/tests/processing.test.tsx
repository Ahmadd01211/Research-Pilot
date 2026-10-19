import { afterEach, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppRoutes } from '../src/app/router';

const project = '11111111-1111-4111-8111-111111111111';
const document = '22222222-2222-4222-8222-222222222222';
const base = `/projects/${project}/documents/${document}`;
afterEach(() => vi.unstubAllGlobals());
function open(state = 'extracted', error: string | null = null, detail = false) {
  const paper = { id: document, project_id: project, filename: 'Source.pdf', byte_size: 1000, created_at: '2026-10-19', status: state, processing: { state, attempts: 3, error_code: error, page_count: state === 'extracted' ? 2 : null, extractor_version: 'pypdf:test', completed_at: null } };
  const mock = vi.fn((url: string, init?: RequestInit) => {
    if (url === '/api/v1/me') return Promise.resolve(Response.json({ display_name: 'Researcher', email: 'r@example.com' }));
    if (url === '/api/v1/auth/csrf') return Promise.resolve(Response.json({ csrf_token: 'synthetic' }));
    if (url.includes('/pages/')) { const n = Number(url.split('/').at(-1)); return Promise.resolve(Response.json({ document_id: document, page_number: n, text: n === 1 ? 'First source statement.' : 'Second source statement.', source_sha256: 'original-source-fingerprint', extractor_version: 'pypdf:test' })); }
    if (init?.method === 'POST') { paper.status = 'queued'; paper.processing.state = 'queued'; paper.processing.error_code = null; return Promise.resolve(Response.json(paper)); }
    if (url === `/api/v1${base}`) return Promise.resolve(Response.json(paper));
    if (url.includes('/documents')) return Promise.resolve(Response.json({ items: [paper], total: 1 }));
    return Promise.resolve(Response.json({ id: project, title: 'Research focus', archived_at: null }));
  });
  vi.stubGlobal('fetch', mock);
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={cache}><MemoryRouter initialEntries={[`/projects/${project}/library${detail ? '/' + document : ''}`]}><AppRoutes/></MemoryRouter></QueryClientProvider>);
  return mock;
}
it('links only extracted papers to source text without claiming AI indexing', async () => {
  open();
  expect(await screen.findByRole('link', { name: 'Review extracted text (2 pages)' })).toHaveAttribute('href', `/projects/${project}/library/${document}`);
  expect(screen.getByText('Text extracted')).toBeVisible();
  expect(screen.getByText(/not yet available to Research Chat/)).toBeVisible();
});
it('explains insufficient text and does not offer a pointless retry', async () => {
  open('failed', 'insufficient_text');
  expect(await screen.findByText(/OCR is not available yet/)).toBeVisible();
  expect(screen.queryByRole('button', { name: /Retry extraction/ })).not.toBeInTheDocument();
});
it('submits an authorized retry and shows queued state after success', async () => {
  const mock = open('failed', 'storage_unavailable'); const ui = userEvent.setup();
  await ui.click(await screen.findByRole('button', { name: /Retry extraction/ }));
  expect(await screen.findByText('Queued')).toBeVisible();
  const call = mock.mock.calls.find(([, init]) => init?.method === 'POST');
  expect(call?.[0]).toBe(`/api/v1${base}/retry`);
  expect(call?.[1]?.headers).toMatchObject({ 'x-csrf-token': 'synthetic' });
});
it('navigates physical PDF pages and exposes original source provenance', async () => {
  open('extracted', null, true); const ui = userEvent.setup();
  expect(await screen.findByText('First source statement.')).toBeVisible();
  expect(screen.getByRole('button', { name: 'Previous page' })).toBeDisabled();
  await ui.click(screen.getByRole('button', { name: 'Next page' }));
  expect(await screen.findByText('Second source statement.')).toBeVisible();
  expect(screen.getByRole('button', { name: 'Next page' })).toBeDisabled();
  await ui.click(screen.getByText('Source provenance'));
  expect(screen.getByText(/original-source-fingerprint/)).toBeVisible();
  expect(screen.getByText(/Verify important quotations against the original/)).toBeVisible();
});
