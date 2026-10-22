import { useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, Download, FileDown } from 'lucide-react';
import { Link, useParams } from 'react-router';
import { mutate, read } from '@/lib/api/client';
import { useProject } from '@/features/projects/api';

type Export = { id: string; kind: 'reference_csv' | 'draft_markdown'; draft_id: string | null; filename: string; sha256: string; byte_size: number; created_at: string };
type Draft = { id: string; title: string; revision: number };
type ExportInput = { kind: Export['kind']; draft_id: string | null; expected_revision: number | null; request_id: string };

export function ExportsPage() {
  const { id = '' } = useParams(), project = useProject(id), cache = useQueryClient();
  const [kind, setKind] = useState<Export['kind']>('reference_csv'), [draftId, setDraftId] = useState('');
  const [offset, setOffset] = useState(0), [request, setRequest] = useState<ExportInput | null>(null);
  const history = useQuery({ queryKey: ['exports', id, offset], queryFn: ({ signal }) => read<{ items: Export[]; total: number }>(`/projects/${id}/exports?offset=${offset}`, signal), enabled: !!project.data });
  const drafts = useQuery({ queryKey: ['drafts', id], queryFn: ({ signal }) => read<{ items: Draft[] }>(`/projects/${id}/drafts`, signal), enabled: !!project.data });
  const create = useMutation({ mutationFn: (input: ExportInput) => mutate<Export>(`/projects/${id}/exports`, 'POST', input), onSuccess: async () => { setRequest(null); setOffset(0); await cache.invalidateQueries({ queryKey: ['exports', id] }); } });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const draft = drafts.data?.items.find(item => item.id === draftId);
    if (kind === 'draft_markdown' && !draft) return;
    const input: ExportInput = request ?? { kind, draft_id: kind === 'draft_markdown' ? draftId : null, expected_revision: kind === 'draft_markdown' ? draft!.revision : null, request_id: crypto.randomUUID() };
    setRequest(input); create.mutate(input);
  }
  function changeKind(value: Export['kind']) { setKind(value); setRequest(null); create.reset(); }
  if (project.isPending) return <p role="status">Opening exports…</p>;
  if (project.isError || !project.data) return <section className="card"><h1>Project unavailable</h1><Link className="btn mt16" to="/projects">All projects</Link></section>;
  return <><Link className="back-projects" to={`/projects/${id}`}><ArrowLeft size={14}/>Back to project</Link><div className="page-heading mt24"><div><p className="eyebrow">EXPORTS</p><h1>Download research files</h1><p className="page-subtitle">Create a snapshot, then download the exact same file from history later.</p></div></div>
    <form className="card" onSubmit={submit}><h2>Create export</h2><label className="field mt16">File type<select value={kind} onChange={e => changeKind(e.target.value as Export['kind'])} disabled={!!project.data.archived_at}><option value="reference_csv">Reference records · CSV</option><option value="draft_markdown">Writing draft · Markdown</option></select></label>{kind === 'draft_markdown' && <label className="field mt16">Draft<select value={draftId} onChange={e => { setDraftId(e.target.value); setRequest(null); }} required><option value="">Choose a draft</option>{drafts.data?.items.map(draft => <option key={draft.id} value={draft.id}>{draft.title} · version {draft.revision}</option>)}</select></label>}<p className="muted mt16">CSV contains raw verified metadata, not a style-formatted bibliography. Markdown keeps citation markers as source links, not formatted citations.</p>{create.isError && <p role="alert" className="alert mt16">{create.error.message} You can retry the same export request.</p>}{create.isSuccess && create.data && <p role="status" className="notice mt16">Snapshot created. <a href={`/api/v1/projects/${id}/exports/${create.data.id}/download`}>Download {create.data.filename}</a></p>}<button className="btn primary mt24" type="submit" disabled={!!project.data.archived_at || create.isPending || (kind === 'draft_markdown' && (!draftId || drafts.isPending || drafts.isError))}><FileDown size={15}/>{create.isPending ? 'Creating…' : 'Create snapshot'}</button></form>
    <section className="card mt24"><h2>Export history</h2><p className="muted mt16">Each file is an immutable snapshot. A later edit to a draft or reference does not change an earlier download.</p>{history.isPending ? <p role="status">Loading history…</p> : history.isError ? <button className="btn mt16" onClick={() => void history.refetch()}>Retry history</button> : history.data?.items.length ? <><div className="table-scroll mt16"><table><thead><tr><th scope="col">File</th><th scope="col">Created</th><th scope="col">Size</th><th scope="col">Download</th></tr></thead><tbody>{history.data.items.map(item => <tr key={item.id}><td><strong>{item.filename}</strong><br/><span className="muted tiny">{item.kind === 'reference_csv' ? 'References CSV' : 'Draft Markdown'}</span></td><td>{new Date(item.created_at).toLocaleString()}</td><td>{(item.byte_size / 1024).toFixed(1)} KB</td><td><a className="btn" href={`/api/v1/projects/${id}/exports/${item.id}/download`}><Download size={14}/>Download</a></td></tr>)}</tbody></table></div><div className="row mt16"><button className="btn" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 20))}>Newer</button><span className="tiny muted">{offset + 1}–{offset + history.data.items.length} of {history.data.total}</span><button className="btn" disabled={offset + history.data.items.length >= history.data.total} onClick={() => setOffset(offset + 20)}>Older</button></div></> : <p className="muted mt16">No exports yet.</p>}</section></>;
}
