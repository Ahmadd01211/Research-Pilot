import { useRef, useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, FilePenLine, Plus, Save, Trash2 } from 'lucide-react';
import { Link, useNavigate, useParams } from 'react-router';
import { ApiError, mutate, read } from '@/lib/api/client';
import { useProject } from '@/features/projects/api';

import { useDraftProtection } from './use-draft-protection';
import { DraftNavigationGuard } from './draft-navigation-guard';
import { DraftConflictReview } from './draft-conflict-review';

type Draft = { id: string; title: string; body: string; reference_ids: string[]; revision: number; created_at: string; updated_at: string };
type Version = { revision: number; title: string; body: string; reference_ids: string[]; created_at: string };
type Reference = { id: string; title: string; authors: string[]; year: number | null; document_id: string | null };

function DraftEditor({ projectId, draft, archived }: { projectId: string; draft: Draft; archived: boolean }) {
  const cache = useQueryClient(), navigate = useNavigate(), area = useRef<HTMLTextAreaElement>(null);
  const { title, setTitle, body, setBody, baseline, dirty, acceptSaved, loadLatest, reapplyTo } = useDraftProtection(draft);
  const [conflict, setConflict] = useState<Draft | null>(null);
  const [reviewError, setReviewError] = useState(false);
  const [selectedVersion, setSelectedVersion] = useState<Version | null>(null);
  const [beforeRevision, setBeforeRevision] = useState<number | null>(null);
  const [history, setHistory] = useState<Version[]>([]);
  const [removing, setRemoving] = useState(false);
  const references = useQuery({ queryKey: ['references', projectId], queryFn: ({ signal }) => read<{ items: Reference[] }>(`/projects/${projectId}/references`, signal) });
  const versions = useQuery({ queryKey: ['draft-versions', projectId, draft.id, beforeRevision], queryFn: ({ signal }) => read<{ items: Version[]; next_before_revision: number | null }>(`/projects/${projectId}/drafts/${draft.id}/versions${beforeRevision ? `?before_revision=${beforeRevision}` : ''}`, signal) });
  const save = useMutation({
    mutationFn: (submitted: { title: string; body: string; revision: number }) => mutate<Draft>(`/projects/${projectId}/drafts/${draft.id}`, 'PUT', { title: submitted.title.trim(), body: submitted.body, expected_revision: submitted.revision }),
    onSuccess: async (saved, submitted) => {
      acceptSaved(saved, submitted); setConflict(null); setReviewError(false);
      setSelectedVersion(null); setHistory([]); setBeforeRevision(null);
      cache.setQueryData(['draft', projectId, draft.id], saved);
      await cache.invalidateQueries({ queryKey: ['drafts', projectId] });
      await cache.invalidateQueries({ queryKey: ['draft-versions', projectId, draft.id] });
    },
    onError: async error => {
      if (error instanceof ApiError && error.status === 409) await reviewLatest();
    },
  });
  async function reviewLatest() {
    setReviewError(false);
    try { setConflict(await read<Draft>(`/projects/${projectId}/drafts/${draft.id}`)); }
    catch { setReviewError(true); }
  }
  const remove = useMutation({ mutationFn: () => mutate<void>(`/projects/${projectId}/drafts/${draft.id}/remove`, 'POST', { expected_revision: baseline.revision }), onSuccess: async () => { await cache.invalidateQueries({ queryKey: ['drafts', projectId] }); navigate(`/projects/${projectId}/writing`); } });
  function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); if (!conflict && !reviewError && !save.isPending) save.mutate({ title, body, revision: baseline.revision }); }
  function insertCitation(ref: Reference) {
    const node = area.current, start = node?.selectionStart ?? body.length, end = node?.selectionEnd ?? body.length;
    const marker = `[@${ref.id}]`;
    setBody(body.slice(0, start) + marker + body.slice(end));
    requestAnimationFrame(() => { node?.focus(); node?.setSelectionRange(start + marker.length, start + marker.length); });
  }
  const allVersions = [...history, ...(versions.data?.items ?? [])];
  const outline = [...body.matchAll(/^#{1,3}\s+(.+)$/gm)].map(match => ({ heading: match[1], level: match[0].match(/^#+/)?.[0].length ?? 1 }));
  const citedIds = [...body.matchAll(/\[@([0-9a-fA-F-]{36})\]/g)].map(match => match[1]);
  const missing = [...new Set(citedIds)].filter(id => !references.data?.items.some(ref => ref.id === id));
  return <><DraftNavigationGuard dirty={dirty || save.isPending}/><div className="page-heading mt24"><div><p className="eyebrow">WRITING STUDIO · RESEARCHER TEXT</p><h1>{draft.title}</h1><p className="page-subtitle">Explicit saves create a new version. Citation markers link to verified reference records.</p></div><span className="badge">{dirty ? 'Unsaved changes' : `Saved · version ${draft.revision}`}</span></div>
    <div className="writing-grid"><aside className="card"><h2>Outline</h2>{outline.length ? <ol className="writing-outline">{outline.map((item, index) => <li key={index} style={{ paddingLeft: (item.level - 1) * 12 }}>{item.heading}</li>)}</ol> : <p className="muted mt16">Start a line with #, ##, or ### to add a heading.</p>}<h2 className="mt24">References</h2>{references.isPending ? <p role="status">Loading references…</p> : references.isError ? <button className="btn mt16" onClick={() => void references.refetch()}>Retry references</button> : references.data?.items.length ? <ul className="writing-references">{references.data.items.map(ref => <li key={ref.id}><strong>{ref.title}</strong><small>{ref.authors.join(', ')}{ref.year ? ` · ${ref.year}` : ''}</small><button className="btn" type="button" disabled={archived} onClick={() => insertCitation(ref)}>Insert citation</button>{ref.document_id && <Link to={`/projects/${projectId}/library/${ref.document_id}`}>Check PDF</Link>}</li>)}</ul> : <p className="muted mt16">Add verified records in <Link to={`/projects/${projectId}/references`}>References</Link> before inserting citations.</p>}{missing.length > 0 && <p role="alert" className="alert mt16">{missing.length} citation marker(s) refer to removed or unavailable records. Review them before saving.</p>}</aside>
      <div><form className="card" onSubmit={submit}><label className="field">Draft title<input value={title} onChange={e => setTitle(e.target.value)} maxLength={180} required disabled={archived}/></label><label className="field mt16">Draft text<textarea ref={area} className="writing-body" value={body} onChange={e => setBody(e.target.value)} maxLength={50000} spellCheck disabled={archived} placeholder="# Introduction\n\nWrite your own analysis here…"/></label><p className="tiny muted mt16">Text and headings use plain Markdown. A marker such as [@reference-id] links a verified record; it is not formatted citation output yet.</p>{save.isError && <div role="alert" className="alert mt16">{save.error.message} Your unsaved text remains in the editor. Review the latest saved version before retrying.</div>}{reviewError && <div role="alert" className="alert mt16">The latest version could not be loaded. Your text is still here. <button className="btn" type="button" onClick={() => void reviewLatest()}>Retry version review</button></div>}{save.isSuccess && !dirty && <p role="status" className="notice mt16">Version saved.</p>}<div className="row wrap mt24"><button className="btn primary" type="submit" disabled={archived || !dirty || save.isPending || !!conflict || reviewError}><Save size={15}/>{save.isPending ? 'Saving…' : 'Save new version'}</button><button className="btn danger" type="button" disabled={archived || remove.isPending} onClick={() => setRemoving(true)}><Trash2 size={14}/>Remove draft</button></div></form>
        {conflict && <DraftConflictReview latest={conflict} title={title} body={body} onKeepMine={() => { reapplyTo(conflict); setConflict(null); save.reset(); }} onLoadLatest={() => { if (window.confirm('Replace your unsaved text with the latest saved version?')) { loadLatest(conflict); setConflict(null); save.reset(); } }}/>}
        <section className="card mt24"><h2>Version history</h2><p className="muted mt16">Select a saved version to inspect it. Restoring copies its text into the editor; you must save it as a new version.</p>{versions.isPending ? <p role="status">Loading versions…</p> : versions.isError ? <button className="btn mt16" onClick={() => void versions.refetch()}>Retry versions</button> : <><ul className="writing-versions">{allVersions.map(version => <li key={version.revision}><button className="btn" onClick={() => setSelectedVersion(version)}>Version {version.revision} · {new Date(version.created_at).toLocaleString()}</button></li>)}</ul>{versions.data?.next_before_revision && <button className="btn mt16" onClick={() => { setHistory(allVersions); setBeforeRevision(versions.data!.next_before_revision); }}>Load earlier versions</button>}</>}{selectedVersion && <div className="writing-version-preview mt24"><h3>Version {selectedVersion.revision}: {selectedVersion.title}</h3><pre>{selectedVersion.body}</pre><button className="btn mt16" disabled={archived} onClick={() => { setTitle(selectedVersion.title); setBody(selectedVersion.body); setSelectedVersion(null); }}>Copy into editor</button></div>}</section></div></div>
    {removing && <div className="card mt24"><h2>Remove this draft?</h2><p className="muted mt16">It will leave your active writing list. Its saved versions remain stored for the later removal lifecycle.</p>{remove.isError && <p role="alert" className="alert mt16">{remove.error.message}</p>}<div className="row mt16"><button className="btn" onClick={() => setRemoving(false)}>Keep draft</button><button className="btn danger" disabled={remove.isPending} onClick={() => remove.mutate()}>{remove.isPending ? 'Removing…' : 'Remove draft'}</button></div></div>}</>;
}

export function WritingPage() {
  const { id = '', draftId } = useParams(), project = useProject(id), cache = useQueryClient(), navigate = useNavigate();
  const drafts = useQuery({ queryKey: ['drafts', id], queryFn: ({ signal }) => read<{ items: Draft[] }>(`/projects/${id}/drafts`, signal), enabled: !!project.data });
  const draft = useQuery({ queryKey: ['draft', id, draftId], queryFn: ({ signal }) => read<Draft>(`/projects/${id}/drafts/${draftId}`, signal), enabled: !!project.data && !!draftId });
  const create = useMutation({ mutationFn: () => mutate<Draft>(`/projects/${id}/drafts`, 'POST', { title: 'Untitled draft', body: '' }), onSuccess: async item => { await cache.invalidateQueries({ queryKey: ['drafts', id] }); navigate(`/projects/${id}/writing/${item.id}`); } });
  if (project.isPending) return <p role="status">Opening writing studio…</p>;
  if (!project.data) return <section className="card"><h1>Project unavailable</h1><Link className="btn mt16" to="/projects">All projects</Link></section>;
  return <><Link className="back-projects" to={draftId ? `/projects/${id}/writing` : `/projects/${id}`}><ArrowLeft size={14}/>{draftId ? 'All drafts' : 'Back to project'}</Link>{draftId ? draft.isPending ? <p role="status" className="mt24">Loading draft…</p> : !draft.data ? <div role="alert" className="alert mt24">Draft unavailable. <Link to={`/projects/${id}/writing`}>All drafts</Link></div> : <DraftEditor key={draft.data.id} projectId={id} draft={draft.data} archived={!!project.data.archived_at}/> : <><div className="page-heading mt24"><div><p className="eyebrow">WRITING STUDIO</p><h1>Research drafts</h1><p className="page-subtitle">Write your own work with saved versions and reference links.</p></div><button className="btn primary" disabled={!!project.data.archived_at || create.isPending} onClick={() => create.mutate()}><Plus size={16}/>{create.isPending ? 'Creating…' : 'New draft'}</button></div>{create.isError && <p role="alert" className="alert">{create.error.message}</p>}{drafts.isPending ? <p role="status">Loading drafts…</p> : drafts.isError ? <button className="btn" onClick={() => void drafts.refetch()}>Retry drafts</button> : drafts.data?.items.length ? <div className="gap-list">{drafts.data.items.map(item => <article className="card" key={item.id}><FilePenLine size={20}/><h2>{item.title}</h2><p className="muted tiny">Version {item.revision} · Saved {new Date(item.updated_at).toLocaleString()}</p><Link className="btn mt16" to={`/projects/${id}/writing/${item.id}`}>Open draft</Link></article>)}</div> : <div className="card project-empty"><FilePenLine size={28}/><h2>No drafts yet</h2><p>Create a draft when you are ready to turn reviewed evidence into your own writing.</p></div>}</>}</>;
}
