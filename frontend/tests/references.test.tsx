import { afterEach, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppRoutes } from '../src/app/router';

const projectId = '11111111-1111-4111-8111-111111111111';
const referenceId = '33333333-3333-4333-8333-333333333333';
const reference = { id: referenceId, kind: 'journal', title: '<img src=x onerror=alert(1)>', authors: ['A. Scholar'], year: null, container_title: 'Journal', doi: null, url: '', document_id: null, revision: 1 };
const preview = {
  style: 'apa7', style_label: 'APA 7th edition', preview: true,
  limitations: ['Limited preview: check every entry against the official style manual before use.'],
  items: [{ reference_id: referenceId, text: 'A. Scholar. (n.d.). <img src=x onerror=alert(1)>. Journal.', warnings: ['Author "A. Scholar" has no comma, so it is shown exactly as entered.'],
    segments: [{ text: 'A. Scholar. (n.d.). <img src=x onerror=alert(1)>.', italic: false }, { text: 'Journal', italic: true }, { text: '.', italic: false }] }],
};
afterEach(() => vi.unstubAllGlobals());

function mount(bibliography: () => Promise<Response>, items: unknown[] = [reference]) {
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    if (url === '/api/v1/me') return Promise.resolve(Response.json({ display_name: 'Researcher', email: 'r@example.com' }));
    if (url.endsWith('/references/bibliography')) return bibliography();
    if (url.endsWith('/references/settings')) return Promise.resolve(Response.json({ style: 'apa7', revision: 0, updated_at: null }));
    if (url.endsWith('/references')) return Promise.resolve(Response.json({ items }));
    return Promise.resolve(Response.json({ id: projectId, title: 'AI adoption', archived_at: null }));
  }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[`/projects/${projectId}/references`]}><AppRoutes/></MemoryRouter></QueryClientProvider>);
}

it('shows formatted entries as plain text with italics, warnings and limitations', async () => {
  const { container } = mount(() => Promise.resolve(Response.json(preview)));
  const section = await screen.findByRole('region', { name: 'Bibliography preview' });
  expect(await within(section).findByText(/Limited preview: APA 7th edition. Review before use./)).toBeInTheDocument();
  expect(within(section).getByText(/check every entry against the official style manual/)).toBeInTheDocument();
  expect(within(section).getByText('Journal').tagName).toBe('EM');
  expect(within(section).getByText(/onerror=alert/)).toBeInTheDocument();
  expect(container.querySelector('img')).toBeNull();
  expect(within(section).getByRole('list', { name: 'Formatting warnings' })).toHaveTextContent('has no comma');
});

it('shows loading, empty and retryable error states', async () => {
  let resolve: (value: Response) => void = () => {};
  const first = mount(() => new Promise(done => { resolve = done; }), []);
  expect(await screen.findByText('Formatting preview…')).toBeInTheDocument();
  resolve(Response.json({ ...preview, items: [] }));
  expect(await screen.findByText('No references to format yet.')).toBeInTheDocument();
  first.unmount();

  let fail = true;
  mount(() => Promise.resolve(fail ? Response.json({ detail: 'Server error' }, { status: 500 }) : Response.json(preview)));
  const retry = await screen.findByRole('button', { name: 'Retry preview' });
  expect(screen.getByRole('alert')).toHaveTextContent('Could not format the bibliography preview.');
  fail = false;
  await userEvent.setup().click(retry);
  expect(await screen.findByText('Journal')).toBeInTheDocument();
});

it('loads and submits verified publication details while editing', async () => {
  const detailed = { ...reference, volume: '12', issue: '3', pages: '45-67', publisher: 'Press', edition: '2nd ed.', article_number: '' };
  const mock = vi.fn((url: string, init?: RequestInit) => {
    if (url.endsWith('/me')) return Promise.resolve(Response.json({ display_name: 'Researcher', email: 'r@example.com' }));
    if (url.endsWith('/csrf')) return Promise.resolve(Response.json({ csrf_token: 'synthetic' }));
    if (url.includes('/duplicates?') || url.includes('/documents?')) return Promise.resolve(Response.json({ items: [] }));
    if (url.endsWith('/bibliography')) return Promise.resolve(Response.json(preview));
    if (url.endsWith('/settings')) return Promise.resolve(Response.json({ style: 'apa7', revision: 0 }));
    if (url.endsWith('/references')) return Promise.resolve(Response.json({ items: [detailed] }));
    if (init?.method === 'PUT') return Promise.resolve(Response.json(detailed));
    return Promise.resolve(Response.json({ id: projectId, title: 'AI adoption', archived_at: null }));
  });
  vi.stubGlobal('fetch', mock);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[`/projects/${projectId}/references`]}><AppRoutes/></MemoryRouter></QueryClientProvider>);
  const ui = userEvent.setup(); await ui.click(await screen.findByRole('button', { name: 'Edit' }));
  expect(screen.getByLabelText('Volume')).toHaveValue('12');
  expect(screen.getByLabelText('Page range')).toHaveValue('45-67');
  await ui.clear(screen.getByLabelText('Issue')); await ui.type(screen.getByLabelText('Issue'), '4');
  await ui.click(screen.getByRole('button', { name: 'Save reference' }));
  const call = mock.mock.calls.find(([, init]) => init?.method === 'PUT');
  expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({ volume: '12', issue: '4', pages: '45-67', publisher: 'Press', expected_revision: 1 });
});
