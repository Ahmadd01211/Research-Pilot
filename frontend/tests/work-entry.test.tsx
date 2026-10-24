import { afterEach, expect, it, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppRoutes } from '../src/app/router';

const first = '11111111-1111-4111-8111-111111111111';
const second = '22222222-2222-4222-8222-222222222222';
const project = (id: string, title: string) => ({ id, title, description: '', research_questions: [], objectives: [], archived_at: null });
afterEach(() => vi.unstubAllGlobals());

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location">{location.pathname}</output>;
}

function open(path: string, items: ReturnType<typeof project>[]) {
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    if (url === '/api/v1/me') return Promise.resolve(Response.json({ display_name: 'Researcher', email: 'r@example.com' }));
    if (url.includes('/api/v1/projects?')) return Promise.resolve(Response.json({ items, total: items.length, next_cursor: null }));
    if (url.includes('/api/v1/projects/')) return Promise.resolve(Response.json(items[0]));
    return Promise.resolve(Response.json({ items: [] }));
  }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><AppRoutes/><LocationProbe/></MemoryRouter></QueryClientProvider>);
}

it('opens evidence directly when the researcher has one active project', async () => {
  open('/find-evidence', [project(first, 'AI adoption')]);
  await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent(`/projects/${first}/evidence`));
});

it('lets the researcher choose a project for writing without opening its overview', async () => {
  open('/write', [project(first, 'AI adoption'), project(second, 'Policy review')]);
  expect(await screen.findByRole('heading', { name: 'Continue writing' })).toBeVisible();
  expect(screen.getByRole('link', { name: /AI adoption/ })).toHaveAttribute('href', `/projects/${first}/writing`);
  expect(screen.getByRole('link', { name: /Policy review/ })).toHaveAttribute('href', `/projects/${second}/writing`);
});

it('offers project creation when there is no active project', async () => {
  open('/find-evidence', []);
  expect(await screen.findByRole('link', { name: 'Create project' })).toHaveAttribute('href', '/projects/new');
});

it('shows direct evidence and writing links on a dashboard project card', async () => {
  open('/dashboard', [project(first, 'AI adoption')]);
  const card = (await screen.findByRole('heading', { name: 'AI adoption' })).closest('article');
  expect(card).not.toBeNull();
  expect(within(card!).getByRole('link', { name: 'Find evidence' })).toHaveAttribute('href', `/projects/${first}/evidence`);
  expect(within(card!).getByRole('link', { name: 'Write' })).toHaveAttribute('href', `/projects/${first}/writing`);
});
