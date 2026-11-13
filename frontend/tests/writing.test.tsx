import { afterEach, expect, it, vi } from 'vitest';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppRoutes } from '../src/app/router';

const projectId = '11111111-1111-4111-8111-111111111111';
const draftId = '22222222-2222-4222-8222-222222222222';
const referenceId = '33333333-3333-4333-8333-333333333333';
afterEach(() => vi.unstubAllGlobals());

const initialDraft = { id: draftId, title: 'Review', body: '# Introduction\n', reference_ids: [], revision: 1, created_at: '2026-10-21T00:00:00Z', updated_at: '2026-10-21T00:00:00Z' };

function openEditor(save?: (init: RequestInit) => Promise<Response>) {
  let stored = { ...initialDraft };
  let readFails = false;
  vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
    if (url === '/api/v1/me') return Promise.resolve(Response.json({ display_name: 'Researcher', email: 'r@example.com' }));
    if (url === '/api/v1/auth/csrf') return Promise.resolve(Response.json({ csrf_token: 'synthetic' }));
    if (url.endsWith(`/drafts/${draftId}`) && init?.method === 'PUT') return save!(init);
    if (url.endsWith('/versions')) return Promise.resolve(Response.json({ items: [stored], next_before_revision: null }));
    if (url.endsWith(`/drafts/${draftId}`)) return Promise.resolve(readFails ? Response.json({ detail: 'Temporarily unavailable' }, { status: 503 }) : Response.json(stored));
    if (url.endsWith('/references') || url.endsWith('/drafts')) return Promise.resolve(Response.json({ items: [] }));
    return Promise.resolve(Response.json({ id: projectId, title: 'AI adoption', archived_at: null }));
  }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[`/projects/${projectId}/writing/${draftId}`]}><AppRoutes/></MemoryRouter></QueryClientProvider>);
  return { client, ui: userEvent.setup(), failReads: () => { readFails = true; }, updateStored: (draft: typeof initialDraft) => { stored = draft; } };
}

it('keeps the editor mounted when a background draft refresh fails', async () => {
  const { client, ui, failReads } = openEditor();
  const editor = await screen.findByRole('textbox', { name: 'Draft text' });
  await ui.type(editor, 'Local work');
  failReads();
  await act(async () => { await client.invalidateQueries({ queryKey: ['draft', projectId, draftId] }); });
  await screen.findByText(/The latest draft could not be refreshed/);
  expect(screen.getByRole('textbox', { name: 'Draft text' })).toHaveValue('# Introduction\nLocal work');
});

it('preserves local text when a background refresh receives another saved revision', async () => {
  const { client, ui } = openEditor();
  const editor = await screen.findByRole('textbox', { name: 'Draft text' });
  await ui.clear(editor);
  await ui.type(editor, 'My unsaved analysis');
  await act(async () => {
    client.setQueryData(['draft', projectId, draftId], { ...initialDraft, body: 'Saved in another tab', revision: 2 });
  });
  await screen.findByText(/A newer saved version is available/);
  expect(screen.getByRole('textbox', { name: 'Draft text' })).toHaveValue('My unsaved analysis');
  expect(screen.getByText('Unsaved changes')).toBeInTheDocument();
  await ui.click(screen.getByRole('button', { name: 'Review latest saved version' }));
  expect(screen.getByText('Saved in another tab')).toBeInTheDocument();
  await ui.click(screen.getByRole('button', { name: 'Copy into editor' }));
  expect(screen.getByRole('textbox', { name: 'Draft text' })).toHaveValue('Saved in another tab');
  expect(screen.getByText('Saved · version 2')).toBeInTheDocument();
});

it('keeps edits typed during a save and uses the returned revision for the next save', async () => {
  let resolveSave!: (response: Response) => void;
  let requestBody: { title: string; body: string; expected_revision: number };
  let attempts = 0;
  const { ui, updateStored } = openEditor(init => {
    requestBody = JSON.parse(String(init.body));
    attempts += 1;
    if (attempts === 1) return new Promise(resolve => { resolveSave = resolve; });
    return Promise.resolve(Response.json({ ...initialDraft, ...requestBody, revision: 3 }));
  });
  const editor = await screen.findByRole('textbox', { name: 'Draft text' });
  await ui.clear(editor);
  await ui.type(editor, 'Submitted text');
  await ui.click(screen.getByRole('button', { name: 'Save new version' }));
  await waitFor(() => expect(attempts).toBe(1));
  await ui.type(editor, ' plus later edits');
  updateStored({ ...initialDraft, body: 'Submitted text', revision: 2 });
  await act(async () => { resolveSave(Response.json({ ...initialDraft, body: 'Submitted text', revision: 2 })); });
  await waitFor(() => expect(screen.getByRole('button', { name: 'Save new version' })).toBeEnabled());
  expect(screen.getByRole('textbox', { name: 'Draft text' })).toHaveValue('Submitted text plus later edits');
  await ui.click(screen.getByRole('button', { name: 'Save new version' }));
  await waitFor(() => expect(requestBody).toMatchObject({ expected_revision: 2, body: 'Submitted text plus later edits' }));
});

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
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[`/projects/${projectId}/writing/${draftId}`]}><AppRoutes/></MemoryRouter></QueryClientProvider>);
  const ui = userEvent.setup();
  await ui.click(await screen.findByRole('button', { name: 'Insert citation' }));
  await ui.click(screen.getByRole('button', { name: 'Save new version' }));
  const call = mock.mock.calls.find(([url, init]) => url.endsWith(`/drafts/${draftId}`) && init?.method === 'PUT');
  const saved = JSON.parse(String(call?.[1]?.body));
  expect(saved).toMatchObject({ expected_revision: 1, title: 'Review' });
  expect(String(saved.body)).toContain(`[@${referenceId}]`);
});
