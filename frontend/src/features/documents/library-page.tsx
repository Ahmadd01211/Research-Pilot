import { useRef, useState } from 'react';
import { Link, useParams } from 'react-router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, Download, FileText, Upload } from 'lucide-react';
import { read, uploadPdf } from '@/lib/api/client';
import type { components } from '@/lib/api/schema';
import { useProject } from '@/features/projects/api';

type DocumentPage = components['schemas']['DocumentPage'];
type UploadResult = components['schemas']['UploadResult'];
export function LibraryPage() {
  const { id = '' } = useParams(), project = useProject(id), cache = useQueryClient();
  const [offset, setOffset] = useState(0), [notice, setNotice] = useState(''), [validation, setValidation] = useState('');
  const input = useRef<HTMLInputElement>(null);
  const papers = useQuery({ queryKey: ['documents', id, offset], queryFn: ({ signal }) => read<DocumentPage>(`/projects/${id}/documents?offset=${offset}&limit=25`, signal), enabled: Boolean(project.data) });
  const upload = useMutation({ mutationFn: (file: File) => uploadPdf<UploadResult>(`/projects/${id}/documents`, file), onSuccess: async result => {
    setNotice(result.duplicate ? `“${result.document.filename}” is already in this project. No duplicate was stored.` : `“${result.document.filename}” was stored privately.`);
    setOffset(0);
    await Promise.all([cache.invalidateQueries({ queryKey: ['documents', id] }), cache.invalidateQueries({ queryKey: ['projects', 'activity', id] })]);
  } });
  function choose(file?: File) {
    setValidation(''); setNotice(''); upload.reset();
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.pdf')) { setValidation('Choose a PDF file.'); return; }
    if (file.size > 20 * 1024 * 1024 || file.size === 0) { setValidation('Choose a nonempty PDF no larger than 20 MiB.'); return; }
    upload.mutate(file);
  }
  if (project.isPending) return <p role="status">Opening the library…</p>;
  if (project.isError || !project.data) return <section className="card"><h1>Project unavailable</h1><p className="muted">The project may be unavailable or belong to another account.</p><button className="btn mt16" onClick={() => void project.refetch()}>Try again</button><Link className="btn mt16" to="/projects">All projects</Link></section>;
  return <><Link className="back-projects" to={`/projects/${id}`}><ArrowLeft size={14}/>Back to project</Link><div className="page-heading mt24"><div><p className="eyebrow">PRIVATE RESEARCH LIBRARY</p><h1>Project papers</h1><p className="page-subtitle">{project.data.title}</p></div><div><input ref={input} type="file" accept=".pdf,application/pdf" hidden aria-label="Choose PDF" disabled={upload.isPending || Boolean(project.data.archived_at)} onChange={event => { choose(event.target.files?.[0]); event.target.value = ''; }}/><button className="btn primary" disabled={upload.isPending || Boolean(project.data.archived_at)} onClick={() => input.current?.click()}><Upload size={16}/>{upload.isPending ? 'Uploading…' : 'Upload PDF'}</button></div></div>
    <div className="notice mb24"><FileText size={18}/><p>PDF storage is available. Text extraction and AI indexing are coming next; stored papers are not yet available to Research Chat. Limit: 20 MiB per PDF, 100 papers or 200 MiB per project.</p></div>
    {project.data.archived_at && <p className="archive-notice">This project is archived. Restore it to upload papers. Existing originals remain available.</p>}
    {upload.isPending && <p role="status" className="notice mb24">Uploading your original PDF. Please keep this page open.</p>}
    {notice && <p role="status" className="notice mb24">{notice}</p>}
    {(validation || upload.isError) && <p role="alert" className="alert mb24">{validation || upload.error?.message}</p>}
    <section className="card"><div className="between"><h2>Original documents</h2>{papers.data && <span className="badge">{papers.data.total} papers</span>}</div>
    {papers.isPending ? <p className="muted mt24" role="status">Loading papers…</p> : papers.isError ? <div role="alert" className="mt24"><p>We couldn’t load your library.</p><button className="btn mt16" onClick={() => void papers.refetch()}>Retry library</button></div> : !papers.data.items.length ? <div className="project-empty"><FileText size={28}/><h2>{offset ? 'No papers on this page' : 'Build your evidence library'}</h2><p className="muted">Upload an original PDF to keep it private to this project.</p></div> : <div className="library-table-scroll"><table className="library-table"><caption className="sr-only">Private PDF documents stored in this project</caption><thead><tr><th scope="col">Paper</th><th scope="col">Size</th><th scope="col">Added</th><th scope="col">Status</th><th scope="col">Original</th></tr></thead><tbody>{papers.data.items.map(paper => <tr key={paper.id}><th scope="row">{paper.filename}</th><td>{(paper.byte_size / 1024).toFixed(1)} KiB</td><td><time dateTime={paper.created_at}>{new Date(paper.created_at).toLocaleDateString()}</time></td><td><span className="badge">Stored</span></td><td><a className="btn" aria-label={`Download ${paper.filename}`} href={`/api/v1/projects/${id}/documents/${paper.id}/download`}><Download size={14}/><span>Download<span className="sr-only"> {paper.filename}</span></span></a></td></tr>)}</tbody></table></div>}
    {papers.data && (offset > 0 || offset + 25 < papers.data.total) && <div className="between mt24"><button className="btn" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset-25))}>Previous</button><span className="muted tiny">Page {Math.floor(offset/25)+1}</span><button className="btn" disabled={offset+25 >= papers.data.total} onClick={() => setOffset(offset+25)}>Next</button></div>}
    </section></>;
}
