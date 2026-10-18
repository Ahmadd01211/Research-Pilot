import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
import type { components } from '@/lib/api/schema';
import { read } from '@/lib/api/client';
export type Project = components['schemas']['ProjectRead'];
export type ProjectPage = components['schemas']['ProjectPage'];
export type ActivityPage = components['schemas']['ActivityPage'];
export type ProjectStatus = 'active' | 'archived' | 'all';
export const projectKey = (id: string) => ['projects', 'detail', id] as const;
export function useProjects(status: ProjectStatus = 'active', search = '', limit = 12) {
  return useInfiniteQuery({
    queryKey: ['projects', 'list', status, search, limit], initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) => { const params = new URLSearchParams({ status, search, limit: String(limit) }); if (pageParam) params.set('cursor', pageParam); return read<ProjectPage>('/projects?' + params, signal); },
    getNextPageParam: last => last.next_cursor ?? undefined,
  });
}
export function useProject(id: string) { return useQuery({ queryKey: projectKey(id), queryFn: ({ signal }) => read<Project>(`/projects/${id}`, signal), enabled: !!id }); }
export function useProjectActivity(id: string) {
  return useInfiniteQuery({ queryKey: ['projects', 'activity', id], initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) => read<ActivityPage>(`/projects/${id}/activity?limit=10${pageParam ? '&cursor=' + encodeURIComponent(pageParam) : ''}`, signal),
    getNextPageParam: last => last.next_cursor ?? undefined, enabled: !!id,
  });
}
