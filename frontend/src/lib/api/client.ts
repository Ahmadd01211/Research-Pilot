import type { components } from './schema';
export type User = components['schemas']['UserRead'];
export async function uploadPdf<T>(path: string, file: File): Promise<T> {
  const token = await read<{ csrf_token: string }>('/auth/csrf');
  return decode<T>(await fetch(`/api/v1${path}?filename=${encodeURIComponent(file.name)}`, { method: 'POST', credentials: 'same-origin', cache: 'no-store', headers: { 'content-type': 'application/pdf', 'x-csrf-token': token.csrf_token }, body: file }));
}
type Json = Record<string, unknown>;
export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); this.name = 'ApiError'; }
}
async function decode<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    const problemDetail = body && typeof body === 'object' && 'detail' in body && typeof body.detail === 'string' ? body.detail : null;
    const detail = problemDetail ?? (response.status === 502 || response.status === 503
      ? 'The app cannot reach the service right now. Please retry in a moment.'
      : response.status === 504
        ? 'The service took too long to respond. Please retry.'
        : `The request could not be completed (${response.status}).`);
    throw new ApiError(detail, response.status);
  }
  return response.status === 204 ? undefined as T : response.json() as Promise<T>;
}
export async function read<T>(path: string, signal?: AbortSignal): Promise<T> {
  return decode<T>(await fetch(`/api/v1${path}`, { credentials: 'same-origin', cache: 'no-store', signal }));
}
export async function mutate<T>(path: string, method: 'POST' | 'PUT' | 'PATCH' | 'DELETE', body?: Json): Promise<T> {
  const token = await read<{ csrf_token: string }>('/auth/csrf');
  return decode<T>(await fetch(`/api/v1${path}`, { method, credentials: 'same-origin', cache: 'no-store', headers: { 'content-type': 'application/json', 'x-csrf-token': token.csrf_token }, body: body ? JSON.stringify(body) : undefined }));
}
