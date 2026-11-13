import { describe, expect, it, vi, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppRoutes } from '../src/app/router';
import { changePasswordSchema, resetPasswordSchema } from '../src/features/auth/schemas';

afterEach(() => vi.unstubAllGlobals());
const user = { id: 'synthetic-user', display_name: 'Researcher', email: 'researcher@example.com' };
const token = 'synthetic-reset-token-0123456789abcdef';
function open(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><AppRoutes/></MemoryRouter></QueryClientProvider>);
}
function api(responses: Record<string, () => Response>) {
  const mock = vi.fn<(url: string, init?: RequestInit) => Promise<Response>>((url) => Promise.resolve((responses[url.replace('/api/v1', '')] ?? (() => Response.json({ detail: 'Unexpected' }, { status: 500 })))()));
  vi.stubGlobal('fetch', mock);
  return mock;
}
const csrf = () => Response.json({ csrf_token: 'synthetic' });
const body = (mock: ReturnType<typeof api>, path: string) => JSON.parse(String(mock.mock.calls.find(([url]) => url === `/api/v1${path}`)?.[1]?.body)) as Record<string, string>;

describe('password schemas', () => {
  it('require matching twelve-character new passwords', () => {
    expect(resetPasswordSchema.safeParse({ new_password: 'long-enough-pass', confirm_password: 'different-pass!' }).success).toBe(false);
    expect(resetPasswordSchema.safeParse({ new_password: 'short', confirm_password: 'short' }).success).toBe(false);
    expect(changePasswordSchema.safeParse({ current_password: 'x', new_password: 'long-enough-pass', confirm_password: 'long-enough-pass' }).success).toBe(true);
  });
});

describe('password recovery and change', () => {
  it('links sign-in to recovery and shows a neutral confirmation after requesting a link', async () => {
    const mock = api({ '/auth/csrf': csrf, '/auth/password/forgot': () => new Response(null, { status: 204 }) });
    open('/login'); const ui = userEvent.setup();
    await ui.click(screen.getByRole('link', { name: 'Forgot password?' }));
    await ui.type(await screen.findByLabelText('Email address'), user.email);
    await ui.click(screen.getByRole('button', { name: 'Send reset link' }));
    expect(await screen.findByRole('status')).toHaveTextContent(`If an account exists for ${user.email}`);
    expect(body(mock, '/auth/password/forgot')).toEqual({ email: user.email });
  });
  it('surfaces missing server email configuration instead of claiming success', async () => {
    api({ '/auth/csrf': csrf, '/auth/password/forgot': () => Response.json({ detail: 'Password recovery email is not configured on this server' }, { status: 503 }) });
    open('/forgot-password'); const ui = userEvent.setup();
    await ui.type(screen.getByLabelText('Email address'), user.email);
    await ui.click(screen.getByRole('button', { name: 'Send reset link' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('not configured');
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });
  it('explains an incomplete reset link', () => {
    const mock = api({}); open('/reset-password');
    expect(screen.getByRole('heading', { name: 'This reset link is incomplete.' })).toBeVisible();
    expect(mock).not.toHaveBeenCalled();
  });
  it('validates the new password locally, then resets with the emailed token and returns to sign in', async () => {
    const mock = api({ '/auth/csrf': csrf, '/auth/password/reset': () => new Response(null, { status: 204 }) });
    open(`/reset-password#token=${token}`); const ui = userEvent.setup();
    await ui.type(screen.getByLabelText('New password'), 'Another-synthetic-456');
    await ui.type(screen.getByLabelText('Confirm new password'), 'Another-synthetic-457');
    await ui.click(screen.getByRole('button', { name: 'Set new password' }));
    expect(await screen.findByText('Passwords do not match')).toBeVisible(); expect(mock).not.toHaveBeenCalled();
    await ui.clear(screen.getByLabelText('Confirm new password'));
    await ui.type(screen.getByLabelText('Confirm new password'), 'Another-synthetic-456');
    await ui.click(screen.getByRole('button', { name: 'Set new password' }));
    expect(await screen.findByText('Password updated. Sign in with your new password.')).toBeVisible();
    expect(body(mock, '/auth/password/reset')).toEqual({ token, new_password: 'Another-synthetic-456' });
  });
  it('offers a new link when the reset token is rejected', async () => {
    api({ '/auth/csrf': csrf, '/auth/password/reset': () => Response.json({ detail: 'This reset link is invalid or has expired. Request a new one.' }, { status: 400 }) });
    open(`/reset-password#token=${token}`); const ui = userEvent.setup();
    await ui.type(screen.getByLabelText('New password'), 'Another-synthetic-456');
    await ui.type(screen.getByLabelText('Confirm new password'), 'Another-synthetic-456');
    await ui.click(screen.getByRole('button', { name: 'Set new password' }));
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('invalid or has expired');
    expect(screen.getByRole('link', { name: 'Request a new link' })).toHaveAttribute('href', '/forgot-password');
  });
  it('changes the password from account settings without sending the confirmation field', async () => {
    const mock = api({ '/me': () => Response.json(user), '/auth/csrf': csrf, '/me/password': () => new Response(null, { status: 204 }) });
    open('/profile'); const ui = userEvent.setup();
    await ui.type(await screen.findByLabelText('Current password'), 'Synthetic-password-123');
    await ui.type(screen.getByLabelText('New password'), 'Another-synthetic-456');
    await ui.type(screen.getByLabelText('Confirm new password'), 'Another-synthetic-456');
    await ui.click(screen.getByRole('button', { name: 'Change password' }));
    expect(await screen.findByRole('status')).toHaveTextContent('Other devices have been signed out.');
    expect(body(mock, '/me/password')).toEqual({ current_password: 'Synthetic-password-123', new_password: 'Another-synthetic-456' });
    expect(screen.getByLabelText('Current password')).toHaveValue('');
  });
});
