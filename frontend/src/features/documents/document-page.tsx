import { lazy, Suspense, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { components } from '@/lib/api/schema';
import { mutate, read } from '@/lib/api/client';
const PdfCanvas = lazy(() => import('./pdf-canvas'));
type Paper = components['schemas']['DocumentRead'];
type Page = components['schemas']['EvidencePage'];
const noBoxes: readonly [number,number,number,number][] = [];

export function DocumentPage() {
  const { id = '', documentId = '' } = useParams();
  const [params, setParams] = useSearchParams();
  const requested = Number(params.get('page') ?? '1');
  const validPage = Number.isInteger(requested) && requested >= 1 && requested <= 300;
  const page = validPage ? requested : 1;
  const [textMode, setTextMode] = useState<'readable'|'raw'>('readable');
  const [view, setView] = useState<'both'|'pdf'|'text'>('both');
  const cache = useQueryClient(), base = `/projects/${id}/documents/${documentId}`;
  const paper = useQuery({ queryKey: ['document', id, documentId], queryFn: ({ signal }) => read<Paper>(base, signal), refetchInterval: query => ['queued','processing'].includes(query.state.data?.status ?? '') ? 3000 : false });
  const project = useQuery({ queryKey: ['projects', 'detail', id], queryFn: ({ signal }) => read<components['schemas']['ProjectRead']>(`/projects/${id}`,signal) });
  const evidence = useQuery({ queryKey: ['evidence', id, documentId, page], queryFn: ({ signal }) => read<Page>(`${base}/pages/${page}`, signal), enabled: paper.data?.status === 'extracted' });
  const prepare = useMutation({ mutationFn: () => mutate<Paper>(`${base}/prepare-reader`, 'POST'), onSuccess: async result => { cache.setQueryData(['document',id,documentId],result); await Promise.all([cache.invalidateQueries({queryKey:['evidence',id,documentId]}),cache.invalidateQueries({queryKey:['documents',id]})]); } });
  const layout = evidence.data?.layout;
  const selected = layout?.passages.findIndex(item => item.id === params.get('passage')) ?? -1;
  const sourceMismatch = Boolean(evidence.data && ((params.has('source') && params.get('source') !== evidence.data.source_sha256) || (params.has('reader') && params.get('reader') !== layout?.version) || (params.has('passage') && layout && selected < 0)));
  const passage = !sourceMismatch && layout && Number.isInteger(selected) ? layout.passages[selected] : undefined;
  const boxes = passage && layout ? passage.word_indices.map(i => layout.words[i].box) : noBoxes;
  function turn(n: number) { const next = new URLSearchParams(params); next.set('page',String(n)); next.delete('passage'); setParams(next); }
  function highlight(index: number) { const next = new URLSearchParams(params); next.set('page',String(page)); if(layout) next.set('passage',layout.passages[index].id); if(evidence.data) next.set('source',evidence.data.source_sha256); if(layout) next.set('reader',layout.version); setParams(next); setView('both'); }
  if (paper.data?.status === 'extracted' && (!validPage || page > (paper.data.processing?.page_count ?? 0))) return <section className="card" role="alert"><h1>Source page unavailable</h1><p>This link does not identify a page in this PDF.</p><Link className="btn mt16" to={`/projects/${id}/library/${documentId}`}>Open first page</Link></section>;
  return <><Link className="back-projects" to={`/projects/${id}/library`}>← Back to library</Link><div className="page-heading mt24"><div><p className="eyebrow">SOURCE READER</p><h1>{paper.data?.filename ?? 'Document evidence'}</h1><p className="page-subtitle">Original PDF alongside readable source text. Physical PDF page numbers, not printed page labels.</p></div></div>
    {paper.isPending ? <p role="status">Loading document…</p> : paper.isError ? <div role="alert" className="card"><p>Document unavailable.</p><button className="btn mt16" onClick={() => void paper.refetch()}>Try again</button></div> : paper.data.status !== 'extracted' ? <div className="notice"><p>Extraction has not completed. Check the library for its current status.</p><Link className="btn mt16" to={`/projects/${id}/library`}>Back to processing status</Link></div> : <section className="card source-reader"><div className="between reader-toolbar"><h2>Page {page} of {paper.data.processing?.page_count}</h2><div className="row wrap"><label className="row gap8">View<select aria-label="Reader layout" value={view} onChange={event => setView(event.target.value as typeof view)}><option value="both">PDF and text</option><option value="pdf">PDF only</option><option value="text">Text only</option></select></label><a className="btn" href={`/api/v1${base}/download`}>Download original</a></div></div><p className="muted tiny mt16">Text extraction can lose columns, tables, formulas and reading order. Verify important quotations against the original.</p>
    {sourceMismatch && <p role="alert" className="alert mt16">This link refers to a different source or reader version. Its highlight has been disabled; verify the original.</p>}
    <div className={`source-reader-grid reader-view-${view}`}>
    {view !== 'text' && <Suspense fallback={<p role="status">Loading PDF viewer…</p>}><PdfCanvas url={`/api/v1${base}/download`} sourceHash={evidence.data?.source_sha256} page={page} boxes={boxes}/></Suspense>}
    {view !== 'pdf' && <section className="reader-transcript" aria-label="Extracted source text"><div className="between reader-panel-heading"><h2>Extracted text</h2><div className="row gap8"><button className="btn" aria-pressed={textMode==='readable'} onClick={() => setTextMode('readable')}>Readable</button><button className="btn" aria-pressed={textMode==='raw'} onClick={() => setTextMode('raw')}>Raw</button></div></div>
    {evidence.isPending ? <p role="status" className="mt24">Loading page text…</p> : evidence.isError ? <div role="alert"><p>Page text is unavailable.</p><button className="btn mt16" onClick={() => void evidence.refetch()}>Retry page</button></div> : <>
    {textMode === 'raw' || !layout ? <><pre className="evidence-text" tabIndex={0} aria-label={`Extracted text for page ${page}`}>{evidence.data.text || 'No text was extracted from this page.'}</pre>{!layout && <div className="notice mt16"><p>This earlier extraction has no word coordinates. Prepare its reader to enable readable passages and highlights.</p>{!project.data?.archived_at && <button className="btn mt16" disabled={prepare.isPending || !project.data} onClick={() => prepare.mutate()}>{prepare.isPending ? 'Preparing…' : 'Prepare readable text and highlights'}</button>}{prepare.isError && <p role="alert">{prepare.error.message}</p>}</div>}</> : <div className="readable-passages"><p className="muted tiny">Source words regrouped into passages, not an AI rewrite. Select “Show in PDF” to check their measured location.</p>{layout.passages.length ? layout.passages.map((item,index) => <div key={index} className={`source-passage ${selected===index && !sourceMismatch ? 'selected' : ''}`}><p>{item.text}</p><button className="btn" aria-pressed={selected===index && !sourceMismatch} onClick={() => highlight(index)}>Show passage {index+1} in PDF</button></div>) : <p className="mt24">No readable body text was found on this page. Check the original or raw text.</p>}{layout.excluded_margin_text.length > 0 && <details className="tiny muted mt24"><summary>Repeated margin text excluded from readable passages</summary>{layout.excluded_margin_text.map((text,index) => <p key={index}>{text}</p>)}</details>}</div>}
    <details className="tiny muted mt24"><summary>Source provenance</summary><p className="processing-note">Original SHA-256: {evidence.data.source_sha256}</p><p>Extractor: {evidence.data.extractor_version}</p>{layout && <p>Reader: {layout.version}</p>}</details></>}
    </section>}</div>
    <div className="between mt24"><button className="btn" disabled={page === 1} onClick={() => turn(page-1)}>Previous page</button><span aria-live="polite">Page {page}</span><button className="btn" disabled={page >= (paper.data.processing?.page_count ?? 0)} onClick={() => turn(page+1)}>Next page</button></div></section>}</>;
}
