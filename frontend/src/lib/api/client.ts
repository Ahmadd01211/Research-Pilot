import type { components } from './schema';
export type User = components['schemas']['UserRead'];
type Json = Record<string, unknown>;
export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); this.name = 'ApiError'; }
}
async function decode<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    const detail = body && typeof body === 'object' && 'detail' in body && typeof body.detail === 'string' ? body.detail : 'The request could not be completed';
    throw new ApiError(detail, response.status);
  }
  return response.status === 204 ? undefined as T : response.json() as Promise<T>;
}
export async function read<T>(path: string, signal?: AbortSignal): Promise<T> {
  return decode<T>(await fetch(`/api/v1${path}`, { credentials: 'same-origin', cache: 'no-store', signal }));
}
export async function mutate<T>(path: string, method: 'POST' | 'PATCH', body?: Json): Promise<T> {
  const token = await read<{ csrf_token: string }>('/auth/csrf');
  return decode<T>(await fetch(`/api/v1${path}`, { method, credentials: 'same-origin', cache: 'no-store', headers: { 'content-type': 'application/json', 'x-csrf-token': token.csrf_token }, body: body ? JSON.stringify(body) : undefined }));
}
