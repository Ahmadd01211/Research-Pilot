import { useQuery } from '@tanstack/react-query';
import { ApiError, read, type User } from '@/lib/api/client';
export const sessionKey = ['identity', 'me'] as const;
export function useSession() {
  return useQuery({
    queryKey: sessionKey, staleTime: 30_000,
    queryFn: async ({ signal }): Promise<User | null> => {
      try { return await read<User>('/me', signal); }
      catch (error) { if (error instanceof ApiError && error.status === 401) return null; throw error; }
    },
  });
}
