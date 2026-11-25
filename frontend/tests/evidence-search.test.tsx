import { afterEach, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppRoutes } from '../src/app/router';

const projectId = '11111111-1111-4111-8111-111111111111';
const paperId = '22222222-2222-4222-8222-222222222222';
afterEach(() => vi.unstubAllGlobals());

type Caps = { embedding_enabled: boolean; embedding_provider?: 'google' | 'local'; answer_enabled: boolean; search_mode: 'hybrid' | 'keyword'; answer_model?: string; answers_remaining_today?: number | null; answer_daily_limit?: number; answer_user_daily_limit?: number; answer_data_policy?: string; paperState?: string };
const hybrid: Caps = { embedding_enabled: true, answer_enabled: true, search_mode: 'hybrid', answer_model: 'gemini-3.8-flash', answers_remaining_today: 20, answer_daily_limit: 20 };
const keywordOnly: Caps = { embedding_enabled: false, answer_enabled: false, search_mode: 'keyword', answers_remaining_today: null, answer_daily_limit: 20 };
function open(caps: Caps | boolean, chat = false) {
  const capabilities = typeof caps === 'boolean' ? (caps ? hybrid : keywordOnly) : caps;
  const enabled = true;
  const mock = vi.fn((url: string, init?: RequestInit) => {
    if (url === '/api/v1/me') return Promise.resolve(Response.json({ display_name: 'Researcher', email: 'r@example.com' }));
    if (url === '/api/v1/auth/csrf') return Promise.resolve(Response.json({ csrf_token: 'synthetic' }));
    if (url.endsWith('/evidence/capabilities')) return Promise.resolve(Response.json({ answer_provider: 'openrouter', ...capabilities }));
    if (url.endsWith('/evidence/threads')) return Promise.resolve(Response.json({ items: [{ id: 'thread-one', title: 'First topic', turn_count: 0 }, { id: 'thread-two', title: 'Second topic', turn_count: 0 }] }));
    if (url.endsWith('/evidence/threads/thread-one') || url.endsWith('/evidence/threads/thread-two')) return Promise.resolve(Response.json({ turns: [] }));
    if (url.endsWith('/evidence/indexes')) return Promise.resolve(Response.json({ items: enabled ? [{ document_id: paperId, state: capabilities.paperState ?? 'ready', processed_chunks: 2, total_chunks: 2, error_code: null, search_mode: capabilities.search_mode }] : [] }));
    if (url.includes('/documents?')) return Promise.resolve(Response.json({ items: [{ id: paperId, filename: 'Evidence.pdf', status: 'extracted' }], total: 1 }));
    if (url.endsWith('/evidence/search') && init?.method === 'POST') return Promise.resolve(Response.json({ model: 'gemini-embedding-2', index_format: 'gemini2-qa-v1:l2', hits: [{ chunk_id: 'chunk-1', document_id: paperId, source_sha256: 'abc', reader_version: 'reader-v1', page_number: 9, kind: 'prose', source_id: 'passage-2', text: 'Adoption varied by firm size.', source_metadata: { passage_id: 'passage-2' }, distance: 0.2 }] }));
    return Promise.resolve(Response.json({ id: projectId, title: 'AI adoption', archived_at: null }));
  });
  vi.stubGlobal('fetch', mock);
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}><MemoryRouter initialEntries={[`/projects/${projectId}/${chat ? 'chat' : 'evidence'}`]}><AppRoutes/></MemoryRouter></QueryClientProvider>);
  return mock;
}

it('offers keyword search without embeddings and never offers indexing', async () => {
  const mock = open(keywordOnly), ui = userEvent.setup();
  expect(await screen.findByText(/Keyword search is active/)).toBeVisible();
  expect(screen.queryByRole('button', { name: 'Index paper' })).not.toBeInTheDocument();
  expect(await screen.findByText(/Keyword-searchable · 2 chunks/)).toBeVisible();
  await ui.click(screen.getByRole('checkbox'));
  await ui.type(screen.getByLabelText('Research question'), 'How did adoption vary?');
  await ui.click(screen.getByRole('button', { name: 'Find evidence' }));
  expect(await screen.findByText('Adoption varied by firm size.')).toBeVisible();
  expect(mock.mock.calls.some(([url, init]) => url.endsWith('/evidence/search') && init?.method === 'POST')).toBe(true);
});

it('tells researchers that local embeddings keep paper text on this server', async () => {
  open({ ...hybrid, embedding_provider: 'local' });
  expect(await screen.findByText(/computed on this ResearchPilot server/)).toBeVisible();
  expect(screen.queryByText(/sent to Google/)).not.toBeInTheDocument();
});

it('discloses that Google embeddings send chunk text to Google', async () => {
  open({ ...hybrid, embedding_provider: 'google' });
  expect(await screen.findByText(/sent to Google for embeddings/)).toBeVisible();
});

it('shows the shared daily answer allowance for OpenRouter answers over keyword evidence', async () => {
  open({ ...keywordOnly, answer_enabled: true, answer_model: 'meta-llama/llama-3.3-70b-instruct:free', answers_remaining_today: 3 }, true);
  expect(await screen.findByText(/3 of 20 shared answers left today/)).toBeVisible();
  expect(screen.queryByText(/Research answers are not configured/)).not.toBeInTheDocument();
});

it('offers a readable-text refresh for papers from an older reader in keyword mode', async () => {
  const mock = open({ ...keywordOnly, paperState: 'needs_refresh' }), ui = userEvent.setup();
  expect(await screen.findByText(/Readable text needs a refresh/)).toBeVisible();
  expect(screen.getByRole('checkbox')).toBeDisabled();
  await ui.click(screen.getByRole('button', { name: 'Refresh readable text' }));
  expect(mock.mock.calls.some(([url, init]) => url.endsWith(`/documents/${paperId}/index`) && init?.method === 'POST')).toBe(true);
});

it('explains a paper with no searchable evidence instead of calling it unindexed', async () => {
  open({ ...keywordOnly, paperState: 'no_evidence' });
  expect(await screen.findByText(/No searchable evidence/)).toBeVisible();
  expect(screen.queryByRole('button', { name: 'Refresh readable text' })).not.toBeInTheDocument();
});

it('discloses where OpenRouter sends passages and handles an unknown allowance', async () => {
  open({ ...keywordOnly, answer_enabled: true, answer_model: 'vendor/model:free', answers_remaining_today: null, answer_data_policy: 'no_collection', answer_user_daily_limit: 5 }, true);
  expect(await screen.findByText(/Remaining answers are unknown right now/)).toBeVisible();
  expect(screen.getByText(/only to model hosts that do not collect prompts/)).toBeVisible();
  expect(screen.getByText(/up to 5 per researcher/)).toBeVisible();
});

it('warns when OpenRouter may route to hosts that retain prompts', async () => {
  open({ ...keywordOnly, answer_enabled: true, answer_model: 'vendor/model:free', answers_remaining_today: 4, answer_data_policy: 'collection_allowed' }, true);
  expect(await screen.findByText(/may retain or train on prompts/)).toBeVisible();
});

it('explains when no answer provider is configured', async () => {
  open(keywordOnly, true);
  expect(await screen.findByText(/Research answers are not configured yet/)).toBeVisible();
  expect(screen.queryByText(/Google API key/)).not.toBeInTheDocument();
  expect(await screen.findByRole('button', { name: 'Ask selected papers' })).toBeDisabled();
});

it('opens the first saved conversation and lets the researcher switch threads', async () => {
  const mock = open(true, true), ui = userEvent.setup();
  const select = await screen.findByRole('combobox', { name: 'Saved conversation' });
  expect(select).toHaveValue('thread-one');
  expect(mock.mock.calls.some(([url]) => url.endsWith('/evidence/threads/thread-one'))).toBe(true);
  await ui.selectOptions(select, 'thread-two');
  expect(select).toHaveValue('thread-two');
  expect(mock.mock.calls.some(([url]) => url.endsWith('/evidence/threads/thread-two'))).toBe(true);
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
