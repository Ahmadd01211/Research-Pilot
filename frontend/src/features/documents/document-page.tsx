import { useState } from 'react';
import { Link, useParams } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import type { components } from '@/lib/api/schema';
import { read } from '@/lib/api/client';

type Paper = components['schemas']['DocumentRead'];
type Page = components['schemas']['EvidencePage'];
export function DocumentPage() {
  const { id = '', documentId = '' } = useParams();
  const [page, setPage] = useState(1);
  const base = `/projects/${id}/documents/${documentId}`;
  const paper = useQuery({ queryKey: ['document', id, documentId], queryFn: ({ signal }) => read<Paper>(base, signal) });
  const evidence = useQuery({ queryKey: ['evidence', id, documentId, page], queryFn: ({ signal }) => read<Page>(`${base}/pages/${page}`, signal), enabled: paper.data?.status === 'extracted' });
  return <><Link className="back-projects" to={`/projects/${id}/library`}>← Back to library</Link><div className="page-heading mt24"><div><p className="eyebrow">SOURCE TEXT · ORIGINAL PDF</p><h1>{paper.data?.filename ?? 'Document evidence'}</h1><p className="page-subtitle">Extracted text, not an AI summary. Page numbers follow the PDF’s physical page order.</p></div></div>
    {paper.isPending ? <p role="status">Loading document…</p> : paper.isError ? <div role="alert" className="card"><p>Document unavailable.</p><button className="btn mt16" onClick={() => void paper.refetch()}>Try again</button></div> : paper.data.status !== 'extracted' ? <p className="notice">Extraction has not completed. Check the library for its current status.</p> : <section className="card"><div className="between"><h2>Page {page} of {paper.data.processing?.page_count}</h2><a className="btn" href={`/api/v1${base}/download`}>Download original</a></div><p className="muted tiny mt16">Text extraction can lose columns, tables, formulas and reading order. Verify important quotations against the original.</p>
    {evidence.isPending ? <p role="status" className="mt24">Loading page text…</p> : evidence.isError ? <div role="alert"><p>Page text is unavailable.</p><button className="btn mt16" onClick={() => void evidence.refetch()}>Retry page</button></div> : <><pre className="evidence-text" tabIndex={0} aria-label={`Extracted text for page ${page}`}>{evidence.data.text || 'No text was extracted from this page.'}</pre><details className="tiny muted mt24"><summary>Source provenance</summary><p className="processing-note">Original SHA-256: {evidence.data.source_sha256}</p><p>Extractor: {evidence.data.extractor_version}</p></details></>}
    <div className="between mt24"><button className="btn" disabled={page === 1} onClick={() => setPage(p => p-1)}>Previous page</button><span aria-live="polite">Page {page}</span><button className="btn" disabled={page >= (paper.data.processing?.page_count ?? 0)} onClick={() => setPage(p => p+1)}>Next page</button></div></section>}</>;
}
