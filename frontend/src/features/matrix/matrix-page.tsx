import { useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, ArrowUpRight, BookOpen, LoaderCircle, Plus, Save, Trash2 } from 'lucide-react';
import { Link, useParams } from 'react-router';
import { ApiError, mutate, read } from '@/lib/api/client';
import type { components } from '@/lib/api/schema';
import { useProject } from '@/features/projects/api';

type MatrixRead = components['schemas']['MatrixRead'];
type RowRead = components['schemas']['RowRead'];
type SourcePage = components['schemas']['SourcePage'];
type SourceRead = components['schemas']['SourceRead'];
type DocumentPage = components['schemas']['DocumentPage'];
type FieldName = 'question' | 'method' | 'sample' | 'finding' | 'limitation';
type DraftCell = { value: string; chunk_id: string; page: number };
type Draft = Record<FieldName, DraftCell>;
const fields: { key: FieldName; label: string }[] = [
  { key: 'question', label: 'Research question' }, { key: 'method', label: 'Method' },
  { key: 'sample', label: 'Sample / context' }, { key: 'finding', label: 'Finding' },
  { key: 'limitation', label: 'Limitation' },
];
const blank = (): Draft => Object.fromEntries(fields.map(item => [item.key, { value: '', chunk_id: '', page: 1 }])) as Draft;
function draftFrom(row?: RowRead): Draft {
  const result = blank();
  row?.cells.forEach(cell => { result[cell.field] = { value: cell.value, chunk_id: cell.chunk_id, page: cell.page_number }; });
  return result;
}
function MatrixConflictReview({ local, latest, unavailable, missing, onKeep, onLoad, onRetry }: { local: Draft; latest: RowRead | null; unavailable: boolean; missing: boolean; onKeep: () => void; onLoad: () => void; onRetry: () => void }) {
  return <section className="notice mt16" aria-labelledby="matrix-conflict-title"><div><h3 id="matrix-conflict-title">This matrix row changed while you were editing</h3><p className="mt16">Compare your unsaved notes with the latest saved row. Nothing has been overwritten.</p>{unavailable ? <><p role="alert">The latest row could not be loaded. Your unsaved notes are still here.</p><button className="btn mt16" type="button" onClick={onRetry}>Retry conflict review</button></> : missing ? <><p role="alert">This row is no longer available. Your unsaved notes remain below; copy them before closing if you want to keep them.</p><section aria-label="Your unsaved matrix notes" className="mt16">{fields.map(field => <p key={field.key}><strong>{field.label}:</strong> {local[field.key].value || 'Not set'}</p>)}</section></> : latest ? <div className="project-form-grid mt16"><section aria-label="Your unsaved matrix notes"><h4>Your unsaved notes</h4>{fields.map(field => <p key={field.key}><strong>{field.label}:</strong> {local[field.key].value || 'Not set'}</p>)}</section><section aria-label="Latest saved matrix notes"><h4>Latest saved notes</h4>{fields.map(field => <p key={field.key}><strong>{field.label}:</strong> {latest.cells.find(cell => cell.field === field.key)?.value || 'Not set'}</p>)}</section></div> : <p role="status">Loading the latest saved row…</p>}{latest && <div className="row wrap mt16"><button className="btn primary" type="button" onClick={onKeep}>Keep my edits</button><button className="btn" type="button" onClick={onLoad}>Load the latest saved row</button></div>}</div></section>;
}
function sourceUrl(projectId: string, documentId: string, source: { source_sha256: string; reader_version: string; page_number: number; kind: string; source_metadata: Record<string, unknown> }) {
  const params = new URLSearchParams({ page: String(source.page_number), source: source.source_sha256, reader: source.reader_version });
  if (source.kind === 'prose' && typeof source.source_metadata.passage_id === 'string') params.set('passage', source.source_metadata.passage_id);
  if (source.kind === 'figure_caption' && typeof source.source_metadata.figure_id === 'string') params.set('caption', source.source_metadata.figure_id);
  return `/projects/${projectId}/library/${documentId}?${params}`;
}
function SourceField({ projectId, documentId, name, label, cell, onChange }: { projectId: string; documentId: string; name: FieldName; label: string; cell: DraftCell; onChange: (cell: DraftCell) => void }) {
  const [offset, setOffset] = useState(0);
  const sources = useQuery({ queryKey: ['matrix-sources', projectId, documentId, cell.page, offset], queryFn: ({ signal }) => read<SourcePage>(`/projects/${projectId}/matrix/sources?document_id=${documentId}&page=${cell.page}&offset=${offset}&limit=100`, signal), enabled: !!documentId });
  const selected = sources.data?.items.find(item => item.chunk_id === cell.chunk_id);
  return <div className="matrix-editor-field"><label htmlFor={`matrix-${name}`}>{label}</label><textarea id={`matrix-${name}`} rows={2} maxLength={2000} value={cell.value} onChange={event => onChange({ ...cell, value: event.target.value })} placeholder={`Write your own ${label.toLowerCase()} note from the cited passage`}/>
    <div className="matrix-source-picker"><label>PDF page<input aria-label={`${label} source page`} type="number" min={1} max={300} value={cell.page} onChange={event => { setOffset(0); onChange({ ...cell, page: Math.max(1, Math.min(300, Number(event.target.value) || 1)), chunk_id: '' }); }}/></label><label>Supporting passage<select aria-label={`${label} supporting passage`} value={cell.chunk_id} disabled={!documentId || sources.isPending || sources.isError} onChange={event => onChange({ ...cell, chunk_id: event.target.value })}><option value="">Choose a passage</option>{sources.data?.items.map((source: SourceRead) => <option key={source.chunk_id} value={source.chunk_id}>{source.kind.replaceAll('_', ' ')} · {source.text.slice(0, 105)}</option>)}{cell.chunk_id && !selected && <option value={cell.chunk_id}>Selected passage outside this set; reselect if the source changed</option>}</select></label></div>
    {sources.isPending && documentId && <p role="status" className="tiny muted">Loading page {cell.page} sources…</p>}{sources.isError && <p role="alert" className="tiny alert">Sources unavailable. Try another page or reload.</p>}{sources.data && !sources.data.items.length && <p className="tiny muted">No eligible source chunks in this set.</p>}{sources.data && sources.data.total > 100 && <div className="row mt16"><button type="button" className="btn" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 100))}>Previous passages</button><span className="tiny muted">{offset + 1}–{Math.min(offset + 100, sources.data.total)} of {sources.data.total}</span><button type="button" className="btn" disabled={offset + 100 >= sources.data.total} onClick={() => setOffset(offset + 100)}>Next passages</button></div>}
    {selected && <div className="matrix-source-preview"><strong>Original excerpt · page {selected.page_number}</strong><p>{selected.text}</p><Link className="text-link" to={sourceUrl(projectId, documentId, selected)}>Check in PDF <ArrowUpRight size={14}/></Link></div>}
  </div>;
}
function RowEditor({ projectId, row, papers, archived, onDone }: { projectId: string; row?: RowRead; papers: DocumentPage['items']; archived: boolean; onDone: () => void }) {
  const cache = useQueryClient();
  const [documentId, setDocumentId] = useState(row?.document_id ?? '');
  const [draft, setDraft] = useState<Draft>(() => draftFrom(row));
  const [validation, setValidation] = useState('');
  const [revision, setRevision] = useState(row?.revision);
  const [conflict, setConflict] = useState<{ latest: RowRead | null; local: Draft; unavailable: boolean; missing: boolean } | null>(null);
  const [keptLocal, setKeptLocal] = useState(false);
  async function reviewConflict(local: Draft) {
    if (!row) return;
    setConflict({ latest: null, local, unavailable: false, missing: false });
    try { const latest = await read<MatrixRead>(`/projects/${projectId}/matrix`); const found = latest.items.find(item => item.id === row.id) ?? null; setConflict({ latest: found, local, unavailable: false, missing: !found }); }
    catch { setConflict({ latest: null, local, unavailable: true, missing: false }); }
  }
  const save = useMutation({ mutationFn: (cells: { field: FieldName; value: string; chunk_id: string }[]) => row ? mutate<RowRead>(`/projects/${projectId}/matrix/${row.id}`, 'PUT', { expected_revision: revision, cells }) : mutate<RowRead>(`/projects/${projectId}/matrix`, 'POST', { document_id: documentId, cells }), onSuccess: async () => { await cache.invalidateQueries({ queryKey: ['matrix', projectId] }); onDone(); }, onError: async error => {
    if (row && error instanceof ApiError && error.status === 409) await reviewConflict(structuredClone(draft));
  } });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!documentId) { setValidation('Choose a paper.'); return; }
    const active = fields.filter(item => draft[item.key].value.trim() || draft[item.key].chunk_id);
    if (!active.length) { setValidation('Add at least one source-linked field.'); return; }
    if (active.some(item => !draft[item.key].value.trim() || !draft[item.key].chunk_id)) { setValidation('Every written field needs a supporting passage.'); return; }
    setValidation('');
    save.mutate(active.map(item => ({ field: item.key, value: draft[item.key].value.trim(), chunk_id: draft[item.key].chunk_id })));
  }
  function keepLocal() { if (!conflict?.latest) return; setRevision(conflict.latest.revision); setConflict(null); setKeptLocal(true); save.reset(); }
  function loadLatest() { if (!conflict?.latest) return; setRevision(conflict.latest.revision); setDraft(draftFrom(conflict.latest)); setConflict(null); setKeptLocal(false); save.reset(); }
  return <section className="card matrix-editor"><div className="between"><div><p className="eyebrow">USER-AUTHORED · SOURCE-LINKED</p><h2>{row ? 'Edit matrix row' : 'Add evidence row'}</h2></div><button className="btn" type="button" onClick={onDone}>Close</button></div><p className="muted mt16">Write your interpretation of the source. Select a passage for each field so readers can verify it. Leave unknown fields empty.</p>{conflict && <MatrixConflictReview local={conflict.local} latest={conflict.latest} unavailable={conflict.unavailable} missing={conflict.missing} onKeep={keepLocal} onLoad={loadLatest} onRetry={() => void reviewConflict(conflict.local)}/>} {keptLocal && <p className="notice mt16" role="status">Your edits remain. Review them and save again against the latest row revision.</p>}<form onSubmit={submit}><fieldset disabled={!!conflict} style={{ border: 0, padding: 0, margin: 0 }}><label className="field mt24">Paper<select value={documentId} disabled={!!row} onChange={event => { setDocumentId(event.target.value); setDraft(blank()); }}><option value="">Choose a paper</option>{papers.map(paper => <option key={paper.id} value={paper.id}>{paper.filename}</option>)}</select></label><div className="matrix-editor-grid">{fields.map(item => <SourceField key={item.key} projectId={projectId} documentId={documentId} name={item.key} label={item.label} cell={draft[item.key]} onChange={cell => setDraft(current => ({ ...current, [item.key]: cell }))}/>)}</div></fieldset>{validation && <p role="alert" className="alert mt16">{validation}</p>}{save.isError && !conflict && <p role="alert" className="alert mt16">{save.error.message} Your notes remain here for review.</p>}<div className="row mt24"><button className="btn primary" type="submit" disabled={archived || save.isPending || !!conflict}>{save.isPending ? <><LoaderCircle className="spin" size={15}/>Saving…</> : <><Save size={15}/>Save evidence row</>}</button></div></form></section>;
}
export function MatrixPage() {
  const { id = '' } = useParams(), project = useProject(id), cache = useQueryClient();
  const [editing, setEditing] = useState<RowRead | 'new' | null>(null);
  const [removing, setRemoving] = useState<RowRead | null>(null);
  const matrix = useQuery({ queryKey: ['matrix', id], queryFn: ({ signal }) => read<MatrixRead>(`/projects/${id}/matrix`, signal), enabled: !!project.data });
  const papers = useQuery({ queryKey: ['matrix-papers', id], queryFn: async ({ signal }) => {
    const first = await read<DocumentPage>(`/projects/${id}/documents?offset=0&limit=50`, signal);
    if (first.total <= 50) return first;
    const second = await read<DocumentPage>(`/projects/${id}/documents?offset=50&limit=50`, signal);
    return { items: [...first.items, ...second.items], total: first.total };
  }, enabled: !!project.data });
  const remove = useMutation({ mutationFn: (row: RowRead) => mutate<void>(`/projects/${id}/matrix/${row.id}/remove`, 'POST', { expected_revision: row.revision }), onSuccess: async () => { setRemoving(null); await cache.invalidateQueries({ queryKey: ['matrix', id] }); } });
  if (project.isPending) return <p role="status">Opening literature matrix…</p>;
  if (project.isError || !project.data) return <section className="card"><h1>Project unavailable</h1><Link className="btn mt16" to="/projects">All projects</Link></section>;
  return <><Link className="back-projects" to={`/projects/${id}`}><ArrowLeft size={14}/>Back to project</Link><div className="page-heading mt24"><div><p className="eyebrow">LITERATURE REVIEW</p><h1>Evidence matrix</h1><p className="page-subtitle">Compare studies in a real table, with each written field tied to an original passage.</p></div><button className="btn primary" disabled={!!project.data.archived_at || !!editing} onClick={() => setEditing('new')}><Plus size={16}/>Add evidence row</button></div><div className="notice mb24"><BookOpen size={18}/><p>Matrix notes are written by you. A source link records where you found support; it does not turn an interpretation into a verified fact.</p></div>
    {matrix.isPending || papers.isPending ? <p role="status">Loading papers and matrix…</p> : matrix.isError || papers.isError ? <div role="alert" className="alert">Could not load the matrix. <button className="btn" onClick={() => { void matrix.refetch(); void papers.refetch(); }}>Retry</button></div> : <>{papers.data && papers.data.total > papers.data.items.length && <p className="notice mb24">This project has more than 100 papers. The current picker shows the first 100; search and pagination are still needed.</p>}{editing && <RowEditor key={editing === 'new' ? 'new' : editing.id} projectId={id} row={editing === 'new' ? undefined : editing} papers={papers.data?.items ?? []} archived={!!project.data.archived_at} onDone={() => setEditing(null)}/>}{!matrix.data?.items.length ? <div className="card project-empty"><BookOpen size={28}/><h2>No evidence rows yet</h2><p>Choose a paper, write a note, and link it to a specific passage. The matrix will grow from real source evidence.</p></div> : <div className="matrix-table-wrap"><table className="matrix-table"><caption>Source-linked literature review for {project.data.title}</caption><thead><tr><th scope="col">Paper</th>{fields.map(item => <th scope="col" key={item.key}>{item.label}</th>)}<th scope="col">Actions</th></tr></thead><tbody>{matrix.data.items.map(row => <tr key={row.id}><th scope="row">{row.document_filename}<small>Updated {new Date(row.updated_at).toLocaleDateString()}</small></th>{fields.map(item => { const cell = row.cells.find(value => value.field === item.key); return <td key={item.key}>{cell ? <><p>{cell.value}</p><Link className="text-link" to={sourceUrl(id, row.document_id, cell)}>PDF p. {cell.page_number}<ArrowUpRight size={13}/></Link></> : <span className="muted">—</span>}</td>; })}<td><div className="matrix-actions"><button className="btn" disabled={!!project.data.archived_at || !!editing} onClick={() => setEditing(row)}>Edit</button><button className="btn danger" disabled={!!project.data.archived_at || remove.isPending} onClick={() => setRemoving(row)}><Trash2 size={14}/>Remove</button></div></td></tr>)}</tbody></table></div>}</>}
    {removing && <div className="card mt24"><h2>Remove this matrix row?</h2><p className="muted mt16">It will disappear from the matrix. The original paper and saved source records remain.</p>{remove.isError && <p role="alert" className="alert mt16">{remove.error.message}</p>}<div className="row mt16"><button className="btn" onClick={() => setRemoving(null)}>Keep row</button><button className="btn danger" disabled={remove.isPending} onClick={() => remove.mutate(removing)}>{remove.isPending ? 'Removing…' : 'Remove row'}</button></div></div>}</>;
}
