import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppRoutes } from '../src/app/router';
import { lines, projectFormSchema } from '../src/features/projects/schemas';

const project = { id: '11111111-1111-4111-8111-111111111111', title: 'My research project', description: 'A real saved project', research_questions: ['What is supported?'], objectives: ['Compare studies'], revision: 1, archived_at: null, created_at: '2026-10-18T00:00:00Z', updated_at: '2026-10-18T00:00:00Z' };
const user = { id: 'owner', display_name: 'Researcher', email: 'r@example.com' };
afterEach(() => vi.unstubAllGlobals());
function open(path: string) { const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } }); render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><AppRoutes/></MemoryRouter></QueryClientProvider>); }
function mockFetch(extra: (url: string, init?: RequestInit) => Response) {
  const mock = vi.fn((url: string, init?: RequestInit) => Promise.resolve(url === '/api/v1/me' ? Response.json(user) : url === '/api/v1/auth/csrf' ? Response.json({ csrf_token: 'synthetic' }) : extra(url, init))); vi.stubGlobal('fetch', mock); return mock;
}
describe('research projects', () => {
  it('normalizes research lines and validates bounded input', () => {
    expect(lines(' First question \n\n Second question ')).toEqual(['First question', 'Second question']);
    expect(projectFormSchema.safeParse({ title: ' ', description: '', research_questions: '', objectives: '' }).success).toBe(false);
    expect(projectFormSchema.safeParse({ title: 'Valid', description: '', research_questions: Array(21).fill('Question').join('\n'), objectives: '' }).success).toBe(false);
  });
  it('renders a real empty state and creation route', async () => {
    mockFetch(() => Response.json({ items: [], total: 0, next_cursor: null })); open('/projects');
    expect(await screen.findByText('Start with a question worth exploring.')).toBeVisible();
    expect(screen.getByRole('link', { name: 'Create your first project' })).toHaveAttribute('href', '/projects/new');
  });
  it('submits structured questions and preserves retry identity after a transient failure', async () => {
    const payloads: Record<string, unknown>[] = [];
    mockFetch((url, init) => { if (url === '/api/v1/projects' && init?.method === 'POST') { payloads.push(JSON.parse(String(init.body))); return Response.json({ detail: 'Temporarily unavailable' }, { status: 503 }); } return Response.json({ items: [], total: 0, next_cursor: null }); });
    open('/projects/new'); const ui = userEvent.setup();
    await ui.type(await screen.findByLabelText('Project title'), 'Research focus'); await ui.type(screen.getByLabelText('Research questions'), 'First question{Enter}Second question');
    await ui.click(screen.getByRole('button', { name: 'Create project' })); expect(await screen.findByRole('alert')).toHaveTextContent('Temporarily unavailable');
    await ui.click(screen.getByRole('button', { name: 'Create project' })); expect(payloads).toHaveLength(2); expect(payloads[0].request_id).toBe(payloads[1].request_id); expect(payloads[0].research_questions).toEqual(['First question', 'Second question']);
    expect(screen.getByLabelText('Project title')).toHaveValue('Research focus');
  });
  it('shows archived projects as read-only with a restore action', async () => {
    mockFetch(url => url.endsWith('/activity?limit=10') ? Response.json({ items: [], next_cursor: null }) : Response.json({ ...project, archived_at: '2026-10-18T00:00:00Z' })); open(`/projects/${project.id}`);
    expect(await screen.findByRole('button', { name: 'Restore project' })).toBeVisible(); expect(screen.queryByRole('link', { name: 'Edit project' })).not.toBeInTheDocument(); expect(screen.getByText(/Archived projects are read-only/)).toBeVisible();
  });
  it('keeps a stale edit in the form when the backend rejects its revision', async () => {
    mockFetch((_url, init) => init?.method === 'PATCH' ? Response.json({ detail: 'This project changed. Your edits were not saved.' }, { status: 409 }) : Response.json(project)); open(`/projects/${project.id}/edit`); const ui = userEvent.setup(); const title = await screen.findByLabelText('Project title'); await ui.clear(title); await ui.type(title, 'My unsaved revision'); await ui.click(screen.getByRole('button', { name: 'Save changes' })); expect(await screen.findByRole('alert')).toHaveTextContent('Your edits were not saved'); expect(title).toHaveValue('My unsaved revision');
  });
});


it('requires the exact title before enabling project removal', async () => {
  mockFetch(url => url.endsWith('/activity?limit=10') ? Response.json({ items: [], next_cursor: null }) : Response.json(project));
  open(`/projects/${project.id}`); const ui = userEvent.setup(); await ui.click(await screen.findByRole('button', { name: 'Remove' }));
  const remove = screen.getByRole('button', { name: 'Remove project' }); expect(remove).toBeDisabled();
  await ui.type(screen.getByLabelText(/Type the project title to confirm/), project.title);
  expect(remove).toBeEnabled(); await ui.click(screen.getByRole('button', { name: 'Keep project' }));
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});
