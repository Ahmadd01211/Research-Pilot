import { afterEach, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppRoutes } from '../src/app/router';

const projectId = '11111111-1111-4111-8111-111111111111';
const paperId = '22222222-2222-4222-8222-222222222222';
const cellId = '33333333-3333-4333-8333-333333333333';
afterEach(() => vi.unstubAllGlobals());

it('labels one-paper coverage and keeps candidate claims linked to matrix and PDF evidence', async () => {
  let candidates: unknown[] = [];
  const mock = vi.fn((url: string, init?: RequestInit) => {
    if (url === '/api/v1/me') return Promise.resolve(Response.json({ display_name: 'Researcher', email: 'r@example.com' }));
    if (url === '/api/v1/auth/csrf') return Promise.resolve(Response.json({ csrf_token: 'synthetic' }));
    if (url.endsWith('/matrix')) return Promise.resolve(Response.json({ items: [{ id: 'matrix-row', document_id: paperId, document_filename: 'Paper.pdf', cells: [{ id: cellId, field: 'finding', value: 'Adoption varied by firm size.', page_number: 9 }] }] }));
    if (url.endsWith('/gaps') && init?.method === 'POST') {
      const body = JSON.parse(String(init.body));
      candidates = [{ id: 'gap-1', ...body, revision: 1, created_at: '2026-10-21T00:00:00Z', updated_at: '2026-10-21T00:00:00Z', uncertainty: 'limited_coverage', supporting_papers: 1, evidence: [{ matrix_cell_id: cellId, stance: 'supports', field: 'finding', value: 'Adoption varied by firm size.', document_id: paperId, document_filename: 'Paper.pdf', page_number: 9, source_sha256: 'abc', reader_version: 'reader-v1', kind: 'prose', source_metadata: { passage_id: 'passage-2' }, stale: false }] }];
      return Promise.resolve(Response.json(candidates[0], { status: 201 }));
    }
    if (url.endsWith('/gaps')) return Promise.resolve(Response.json({ items: candidates }));
    return Promise.resolve(Response.json({ id: projectId, title: 'AI adoption', archived_at: null }));
  });
  vi.stubGlobal('fetch', mock);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[`/projects/${projectId}/gaps`]}><AppRoutes/></MemoryRouter></QueryClientProvider>);
  const ui = userEvent.setup();
  await ui.click(await screen.findByRole('button', { name: 'Add candidate' }));
  await ui.type(screen.getByLabelText('Candidate title'), 'Possible context gap');
  await ui.type(screen.getByLabelText('Why this might be a gap'), 'Only the reviewed paper covers this context.');
  await ui.selectOptions(screen.getByLabelText('Evidence role for Paper.pdf finding'), 'supports');
  await ui.click(screen.getByRole('button', { name: 'Save candidate' }));
  const call = mock.mock.calls.find(([url, init]) => url.endsWith('/gaps') && init?.method === 'POST');
  expect(JSON.parse(String(call?.[1]?.body)).evidence).toEqual([{ matrix_cell_id: cellId, stance: 'supports' }]);
  expect(await screen.findByText('Limited coverage')).toBeVisible();
  expect(screen.getByText(/Supporting notes come from one paper/)).toBeVisible();
  expect(screen.getByRole('link', { name: /Check original PDF/ })).toHaveAttribute('href', `/projects/${projectId}/library/${paperId}?page=9&source=abc&reader=reader-v1&passage=passage-2`);
});
