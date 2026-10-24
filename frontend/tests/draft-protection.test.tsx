import { afterEach, expect, it, vi } from 'vitest';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppRoutes } from '../src/app/router';
const pid = '11111111-1111-4111-8111-111111111111', did = '22222222-2222-4222-8222-222222222222';
const original = { id: did, title: 'Review', body: 'Original', reference_ids: [], revision: 1, created_at: '2026-10-21', updated_at: '2026-10-21' };
afterEach(() => vi.unstubAllGlobals());
function setup(conflict: boolean | 'unavailable' = false) {
  let latest = { ...original }; const requests: Record<string, unknown>[] = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith('/me')) return Response.json({ display_name: 'Researcher', email: 'r@example.com' });
    if (url.endsWith('/csrf')) return Response.json({ csrf_token: 'synthetic' });
    if (url.endsWith(`/drafts/${did}`) && init?.method === 'PUT') {
      const data = JSON.parse(String(init.body)); requests.push(data);
      if (conflict === 'unavailable') return Response.json({ detail: 'Service unavailable' }, { status: 503 });
      if (conflict && requests.length === 1) { latest = { ...original, body: 'Other text', revision: 2 }; return Response.json({ detail: 'Draft changed' }, { status: 409 }); }
      latest = { ...latest, title: data.title, body: data.body, revision: latest.revision + 1 }; return Response.json(latest);
    }
    if (url.endsWith('/versions')) return Response.json({ items: [], next_before_revision: null });
    if (url.endsWith(`/drafts/${did}`)) return Response.json(latest);
    if (url.endsWith('/references') || url.endsWith('/drafts')) return Response.json({ items: [] });
    return Response.json({ id: pid, title: 'Project', archived_at: null });
  }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const router = createMemoryRouter([{ path: '*', element: <AppRoutes/> }], { initialEntries: ['/dashboard', `/projects/${pid}/writing/${did}`], initialIndex: 1 });
  render(<QueryClientProvider client={client}><RouterProvider router={router}/></QueryClientProvider>);
  return { client, router, requests };
}
it('protects links and Back until edits are explicitly discarded', async () => {
  const { router } = setup(); const ui = userEvent.setup();
  await ui.type(await screen.findByLabelText('Draft text'), ' mine');
  await ui.click(screen.getByRole('link', { name: 'All drafts' }));
  expect(await screen.findByRole('alertdialog')).toBeVisible();
  await ui.click(screen.getByRole('button', { name: 'Keep editing' }));
  expect(screen.getByLabelText('Draft text')).toHaveValue('Original mine');
  await act(async () => { await router.navigate(-1); });
  expect(await screen.findByRole('alertdialog')).toBeVisible();
  await ui.click(screen.getByRole('button', { name: 'Discard edits and leave' }));
  await waitFor(() => expect(router.state.location.pathname).toBe('/dashboard'));
});
it('preserves edits on refresh and requires conflict review before saving against the new revision', async () => {
  const { client, requests } = setup(true); const ui = userEvent.setup();
  await ui.type(await screen.findByLabelText('Draft text'), ' mine');
  act(() => client.setQueryData(['draft', pid, did], { ...original, body: 'Refresh', revision: 2 }));
  expect(screen.getByLabelText('Draft text')).toHaveValue('Original mine');
  await ui.click(screen.getByRole('button', { name: 'Save new version' }));
  expect(await screen.findByRole('region', { name: 'Review conflicting draft versions' })).toBeVisible();
  expect(screen.getByRole('button', { name: 'Save new version' })).toBeDisabled();
  await ui.click(screen.getByRole('button', { name: 'Keep my text for editing' }));
  await ui.click(screen.getByRole('button', { name: 'Save new version' }));
  await screen.findByText('Version saved.');
  expect(requests[1]).toMatchObject({ expected_revision: 2, body: 'Original mine' });
});
it('confirms replacement of unsaved text', async () => {
  setup(true); const ui = userEvent.setup();
  await ui.type(await screen.findByLabelText('Draft text'), ' mine');
  await ui.click(screen.getByRole('button', { name: 'Save new version' }));
  const button = await screen.findByRole('button', { name: 'Use latest saved text' });
  vi.stubGlobal('confirm', vi.fn(() => false)); await ui.click(button);
  expect(screen.getByLabelText('Draft text')).toHaveValue('Original mine');
  vi.stubGlobal('confirm', vi.fn(() => true)); await ui.click(button);
  expect(screen.getByLabelText('Draft text')).toHaveValue('Other text');
});
it('requests a browser reload warning while dirty', async () => {
  setup(); const ui = userEvent.setup(); await screen.findByLabelText('Draft text');
  const clean = new Event('beforeunload', { cancelable: true }); window.dispatchEvent(clean); expect(clean.defaultPrevented).toBe(false);
  await ui.type(screen.getByLabelText('Draft text'), ' mine');
  const dirty = new Event('beforeunload', { cancelable: true }); window.dispatchEvent(dirty); expect(dirty.defaultPrevented).toBe(true);
});

it('retains text after an ordinary failed save', async () => {
  setup('unavailable'); const ui = userEvent.setup();
  await ui.type(await screen.findByLabelText('Draft text'), ' mine');
  await ui.click(screen.getByRole('button', { name: 'Save new version' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Service unavailable');
  expect(screen.getByLabelText('Draft text')).toHaveValue('Original mine');
  expect(screen.getByRole('button', { name: 'Save new version' })).toBeEnabled();
});
