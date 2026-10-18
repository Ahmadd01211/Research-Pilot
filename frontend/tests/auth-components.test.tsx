import { describe, expect, it, vi, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppRoutes } from '../src/app/router';

afterEach(() => vi.unstubAllGlobals());
const user = { id: 'synthetic-user', display_name: 'Researcher', email: 'researcher@example.com' };
function open(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><AppRoutes/></MemoryRouter></QueryClientProvider>);
  return client;
}
describe('identity flows', () => {
  it('login validates with its own schema and surfaces a safe provider error', async () => {
    const mock = vi.fn().mockResolvedValueOnce(Response.json({ csrf_token: 'synthetic' })).mockResolvedValueOnce(Response.json({ detail: 'Email or password is incorrect' }, { status: 401 })); vi.stubGlobal('fetch', mock);
    open('/login'); const ui = userEvent.setup();
    await ui.type(screen.getByLabelText('Email address'), user.email);
    await ui.type(screen.getByLabelText('Password'), 'short');
    await ui.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Email or password is incorrect');
    expect(mock).toHaveBeenCalledTimes(2);
  });
  it('requires twelve-character registration passwords before making a request', async () => {
    const mock = vi.fn(); vi.stubGlobal('fetch', mock); open('/register'); const ui = userEvent.setup();
    await ui.type(screen.getByLabelText('Full name'), 'Researcher'); await ui.type(screen.getByLabelText('Email address'), user.email); await ui.type(screen.getByLabelText('Password'), 'short'); await ui.click(screen.getByRole('button', { name: 'Create account' }));
    expect(await screen.findByText('Use at least 12 characters')).toBeVisible(); expect(mock).not.toHaveBeenCalled();
  });
  it('redirects an expired or missing session to sign in', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({ detail: 'Please sign in' }, { status: 401 }))); open('/profile');
    expect(await screen.findByRole('button', { name: 'Sign in' })).toBeVisible(); expect(screen.queryByRole('heading', { name: 'Your profile' })).not.toBeInTheDocument();
  });
  it('keeps a service failure distinct from a logged-out state', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({ detail: 'Unavailable' }, { status: 503 }))); open('/profile');
    expect(await screen.findByText('Your account service is unavailable.')).toBeVisible(); expect(screen.queryByRole('button', { name: 'Sign in' })).not.toBeInTheDocument();
  });
  it('updates a real API-backed profile and clears session data after logout', async () => {
    const mock = vi.fn().mockResolvedValueOnce(Response.json(user)).mockResolvedValueOnce(Response.json({ csrf_token: 'csrf-one' })).mockResolvedValueOnce(Response.json({ ...user, display_name: 'Dr. Researcher' })).mockResolvedValueOnce(Response.json({ csrf_token: 'csrf-two' })).mockResolvedValueOnce(new Response(null, { status: 204 })); vi.stubGlobal('fetch', mock);
    const client = open('/profile'); const ui = userEvent.setup(); const input = await screen.findByLabelText('Display name'); await ui.clear(input); await ui.type(input, 'Dr. Researcher'); await ui.click(screen.getByRole('button', { name: 'Save changes' }));
    expect(await screen.findByRole('status')).toHaveTextContent('Your profile has been saved.');
    await ui.click(screen.getByRole('button', { name: 'Sign out' }));
    expect(await screen.findByRole('button', { name: 'Sign in' })).toBeVisible(); await waitFor(() => expect(client.getQueryData(['identity', 'me'])).toBeNull());
  });
});
