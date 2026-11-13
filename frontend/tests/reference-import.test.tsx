import { afterEach, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppRoutes } from '../src/app/router';

const projectId = '11111111-1111-4111-8111-111111111111';
const base = { kind: 'journal', container_title: 'Journal', url: '', errors: [] as string[], warnings: [] as string[], duplicate_of: null as string | null, importable: true };
const candidates = [
  { ...base, index: 0, label: 'good', title: 'Fresh study', authors: ['Lovelace, Ada'], year: 2022, doi: '10.1000/x' },
  { ...base, index: 1, label: 'probable', title: 'Saved study', authors: ['Scholar, Ada'], year: 2020, doi: null, duplicate_of: '44444444-4444-4444-8444-444444444444', warnings: ['Probable duplicate: a reference with the same title and year is already in the project.'] },
  { ...base, index: 2, label: 'bad', title: '<img src=x onerror=alert(1)>', authors: [], year: null, doi: null, importable: false, errors: ['No author is listed.'] },
];
afterEach(() => vi.unstubAllGlobals());
// jsdom 27 lacks Blob.text(), which every supported browser provides.
if (!Blob.prototype.text) Blob.prototype.text = function text(this: Blob) {
  return new Promise<string>(resolve => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result)); reader.readAsText(this); });
};

it('previews a BibTeX file, preselects only clean entries and retries with the same request', async () => {
  let attempts = 0;
  const mock = vi.fn((url: string, init?: RequestInit) => {
    if (url === '/api/v1/me') return Promise.resolve(Response.json({ display_name: 'Researcher', email: 'r@example.com' }));
    if (url === '/api/v1/auth/csrf') return Promise.resolve(Response.json({ csrf_token: 'synthetic' }));
    if (url.endsWith('/references/import/preview')) return Promise.resolve(Response.json({ items: candidates, remaining_capacity: 499 }));
    if (url.endsWith('/references/import') && init?.method === 'POST') {
      attempts += 1;
      return Promise.resolve(attempts === 1 ? Response.json({ detail: 'Temporary failure' }, { status: 503 }) : Response.json({ items: [{}] }, { status: 201 }));
    }
    if (url.endsWith('/references/bibliography')) return Promise.resolve(Response.json({ style: 'apa7', style_label: 'APA', preview: true, limitations: [], items: [] }));
    if (url.endsWith('/references/settings')) return Promise.resolve(Response.json({ style: 'apa7', revision: 0, updated_at: null }));
    if (url.endsWith('/references')) return Promise.resolve(Response.json({ items: [] }));
    return Promise.resolve(Response.json({ id: projectId, title: 'AI adoption', archived_at: null }));
  });
  vi.stubGlobal('fetch', mock);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[`/projects/${projectId}/references`]}><AppRoutes/></MemoryRouter></QueryClientProvider>);
  const ui = userEvent.setup();
  await ui.click(await screen.findByRole('button', { name: 'Import file' }));
  await ui.upload(screen.getByLabelText('Reference file'), new File(['@article{good, title={Fresh study}}'], 'library.ris'));
  expect(screen.getByRole('combobox', { name: 'File format' })).toHaveValue('ris');
  await ui.selectOptions(screen.getByRole('combobox', { name: 'File format' }), 'bibtex');
  await ui.click(screen.getByRole('button', { name: 'Preview entries' }));
  const previewCall = mock.mock.calls.find(([url]) => url.endsWith('/import/preview'));
  expect(JSON.parse(String(previewCall?.[1]?.body))).toEqual({ format: 'bibtex', text: '@article{good, title={Fresh study}}' });
  expect(await screen.findByRole('checkbox', { name: 'Import good' })).toBeChecked();
  expect(screen.getByRole('checkbox', { name: 'Import probable' })).not.toBeChecked();
  expect(screen.getByRole('checkbox', { name: 'Import bad' })).toBeDisabled();
  expect(screen.getByText('<img src=x onerror=alert(1)>')).toBeInTheDocument();
  expect(screen.getByText('No author is listed.')).toBeInTheDocument();
  await ui.click(screen.getByRole('button', { name: 'Import 1 selected' }));
  expect(await screen.findByText(/You can retry the same import/)).toBeInTheDocument();
  await ui.click(screen.getByRole('button', { name: 'Import 1 selected' }));
  expect(await screen.findByText(/Imported 1 references/)).toBeInTheDocument();
  const bodies = mock.mock.calls.filter(([url]) => url.endsWith('/references/import')).map(([, init]) => JSON.parse(String(init?.body)));
  expect(bodies).toHaveLength(2);
  expect(bodies[0].request_id).toBe(bodies[1].request_id);
  expect(bodies[0].items).toEqual([{ kind: 'journal', title: 'Fresh study', authors: ['Lovelace, Ada'], year: 2022, container_title: 'Journal', doi: '10.1000/x', url: '' }]);
});
