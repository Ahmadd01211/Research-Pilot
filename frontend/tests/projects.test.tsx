import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppRoutes } from '../src/app/router';
import { lines, projectFormSchema } from '../src/features/projects/schemas';

const project = { id: '11111111-1111-4111-8111-111111111111', title: 'My research project', description: 'A real saved project', research_questions: ['What is supported?'], objectives: ['Compare studies'], revision: 1, archived_at: null, created_at: '2026-10-18T00:00:00Z', updated_at: '2026-10-18T00:00:00Z' };
const user = { id: 'owner', display_name: 'Researcher', email: 'r@example.com' };
afterEach(() => vi.unstubAllGlobals());
function open(path: string) { const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } }); render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><AppRoutes/></MemoryRouter></QueryClientProvider>); }
function mockFetch(extra: (url: string, init?: RequestInit) => Response | Promise<Response>) {
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
  it('keeps a stale edit visible and compares it with the saved project', async () => {
    const latest = { ...project, title: 'Saved elsewhere', revision: 2 };
    mockFetch((_url, init) => init?.method === 'PATCH' ? Response.json({ detail: 'This project changed. Your edits were not saved.' }, { status: 409 }) : Response.json(latest)); open(`/projects/${project.id}/edit`); const ui = userEvent.setup(); const title = await screen.findByLabelText('Project title'); await ui.clear(title); await ui.type(title, 'My unsaved revision'); await ui.click(screen.getByRole('button', { name: 'Save changes' })); expect(await screen.findByRole('heading', { name: 'This project changed while you were editing' })).toBeVisible(); expect(screen.getByText('Saved elsewhere')).toBeVisible(); expect(title).toHaveValue('My unsaved revision');
  });
  it('shows both versions after a conflict and requires a fresh save for kept edits', async () => {
    let reads = 0; const payloads: Record<string, unknown>[] = [];
    const latest = { ...project, title: 'Saved by another tab', revision: 2 };
    mockFetch((url, init) => {
      if (url === `/api/v1/projects/${project.id}` && !init?.method) return Response.json(++reads === 1 ? project : latest);
      if (url === `/api/v1/projects/${project.id}` && init?.method === 'PATCH') { payloads.push(JSON.parse(String(init.body))); return payloads.length === 1 ? Response.json({ detail: 'This project changed.' }, { status: 409 }) : Response.json({ ...latest, title: 'My unsaved revision', revision: 3 }); }
      return Response.json({ items: [], total: 0, next_cursor: null });
    });
    open(`/projects/${project.id}/edit`); const ui = userEvent.setup();
    const title = await screen.findByLabelText('Project title'); await ui.clear(title); await ui.type(title, 'My unsaved revision');
    await ui.click(screen.getByRole('button', { name: 'Save changes' }));
    expect(await screen.findByRole('heading', { name: 'This project changed while you were editing' })).toBeVisible();
    expect(screen.getByText('Saved by another tab')).toBeVisible(); expect(title).toHaveValue('My unsaved revision');
    await ui.click(screen.getByRole('button', { name: 'Keep my edits' }));
    expect(await screen.findByRole('status')).toHaveTextContent('save again against the latest project version');
    await ui.click(screen.getByRole('button', { name: 'Save changes' }));
    await waitFor(() => expect(payloads).toHaveLength(2));
    expect(payloads).toHaveLength(2); expect(payloads[0].expected_revision).toBe(1); expect(payloads[1].expected_revision).toBe(2); expect(payloads[1].title).toBe('My unsaved revision');
  });
  it('loads the latest saved project only after the user chooses it', async () => {
    let reads = 0; const latest = { ...project, title: 'Latest title', description: 'Latest description', revision: 2 };
    mockFetch((url, init) => {
      if (url === `/api/v1/projects/${project.id}` && !init?.method) return Response.json(++reads === 1 ? project : latest);
      if (url === `/api/v1/projects/${project.id}` && init?.method === 'PATCH') return Response.json({ detail: 'Conflict.' }, { status: 409 });
      return Response.json({ items: [], total: 0, next_cursor: null });
    });
    open(`/projects/${project.id}/edit`); const ui = userEvent.setup();
    const title = await screen.findByLabelText('Project title'); await ui.clear(title); await ui.type(title, 'Local title');
    await ui.click(screen.getByRole('button', { name: 'Save changes' }));
    await screen.findByRole('heading', { name: 'This project changed while you were editing' });
    await ui.click(screen.getByRole('button', { name: 'Load the latest saved version' }));
    expect(title).toHaveValue('Latest title'); expect(screen.getByLabelText('Description')).toHaveValue('Latest description');
    expect(screen.queryByRole('heading', { name: 'This project changed while you were editing' })).not.toBeInTheDocument();
  });
  it('preserves text typed while a project save is in flight', async () => {
    let finish!: (response: Response) => void;
    const pendingResponse = new Promise<Response>(resolve => { finish = resolve; });
    mockFetch((_url, init) => init?.method === 'PATCH' ? pendingResponse : Response.json(project));
    open(`/projects/${project.id}/edit`); const ui = userEvent.setup();
    const title = await screen.findByLabelText('Project title'); await ui.clear(title); await ui.type(title, 'Submitted title');
    await ui.click(screen.getByRole('button', { name: 'Save changes' }));
    await screen.findByRole('button', { name: 'Saving…' });
    const description = screen.getByLabelText('Description'); await ui.clear(description); await ui.type(description, 'Typed after submit');
    finish(Response.json({ ...project, title: 'Submitted title', revision: 2 }));
    expect(await screen.findByText(/Text you entered while saving is still here/)).toBeVisible();
    expect(title).toHaveValue('Submitted title'); expect(description).toHaveValue('Typed after submit');
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
