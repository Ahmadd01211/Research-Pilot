import { useState, type FormEvent } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { FileUp } from 'lucide-react';
import { mutate } from '@/lib/api/client';

type Format = 'bibtex' | 'ris';
type Candidate = { index: number; label: string; kind: string; title: string; authors: string[]; year: number | null; container_title: string; doi: string | null; url: string; importable: boolean; errors: string[]; warnings: string[]; duplicate_of: string | null };
type Preview = { items: Candidate[]; remaining_capacity: number };
type ImportRequest = { request_id: string; items: Omit<Candidate, 'index' | 'label' | 'importable' | 'errors' | 'warnings' | 'duplicate_of'>[] };
const MAX_FILE_BYTES = 1_000_000;
const formatFor = (name: string): Format => /\.ris$/i.test(name) ? 'ris' : 'bibtex';

export function ReferenceImport({ projectId, onDone }: { projectId: string; onDone: () => void }) {
  const cache = useQueryClient();
  const [file, setFile] = useState<File | null>(null), [format, setFormat] = useState<Format>('bibtex');
  const [fileError, setFileError] = useState(''), [selected, setSelected] = useState<Set<number>>(new Set());
  const [request, setRequest] = useState<ImportRequest | null>(null);
  const preview = useMutation({
    mutationFn: async () => mutate<Preview>(`/projects/${projectId}/references/import/preview`, 'POST', { format, text: await file!.text() }),
    onSuccess: data => { setRequest(null); setSelected(new Set(data.items.filter(item => item.importable && !item.duplicate_of).map(item => item.index))); },
  });
  const save = useMutation({
    mutationFn: (input: ImportRequest) => mutate<{ items: unknown[] }>(`/projects/${projectId}/references/import`, 'POST', input),
    onSuccess: async () => { await cache.invalidateQueries({ queryKey: ['references', projectId] }); },
  });
  function choose(next: File | undefined) {
    preview.reset(); save.reset(); setRequest(null);
    if (!next) { setFile(null); return; }
    if (next.size > MAX_FILE_BYTES) { setFile(null); setFileError('Choose a file of at most 1 MB, or split the export into smaller files.'); return; }
    setFileError(''); setFile(next); setFormat(formatFor(next.name));
  }
  function toggle(index: number) {
    const next = new Set(selected);
    if (next.has(index)) next.delete(index); else next.add(index);
    setSelected(next); setRequest(null); save.reset();
  }
  function submitPreview(event: FormEvent<HTMLFormElement>) { event.preventDefault(); if (file) preview.mutate(); }
  function submitImport() {
    const items = preview.data?.items.filter(item => item.importable && selected.has(item.index)) ?? [];
    if (!items.length) return;
    const input = request ?? { request_id: crypto.randomUUID(), items: items.map(({ kind, title, authors, year, container_title, doi, url }) => ({ kind, title, authors, year, container_title, doi, url })) };
    setRequest(input); save.mutate(input);
  }
  const chosen = preview.data?.items.filter(item => item.importable && selected.has(item.index)).length ?? 0;
  const overCapacity = !!preview.data && chosen > preview.data.remaining_capacity;
  return <section className="card mt24" aria-labelledby="reference-import-heading"><div className="between"><h2 id="reference-import-heading">Import BibTeX or RIS</h2><button className="btn" onClick={onDone}>Close</button></div>
    <p className="muted mt16">Nothing is saved until you review the entries and choose Import. Exported metadata can be incomplete or wrong, so check imported records against the publisher.</p>
    <form onSubmit={submitPreview}>
      <label className="field mt16">Reference file<input type="file" accept=".bib,.bibtex,.ris,.txt" onChange={e => choose(e.target.files?.[0])}/></label>
      <label className="field mt16">File format<select value={format} onChange={e => { setFormat(e.target.value as Format); preview.reset(); }}><option value="bibtex">BibTeX (.bib)</option><option value="ris">RIS (.ris)</option></select></label>
      {fileError && <p role="alert" className="alert mt16">{fileError}</p>}{preview.isError && <p role="alert" className="alert mt16">{preview.error.message}</p>}
      <button className="btn mt16" type="submit" disabled={!file || preview.isPending}><FileUp size={15}/>{preview.isPending ? 'Reading…' : 'Preview entries'}</button>
    </form>
    {preview.data && <div className="mt24">
      <p role="status">{preview.data.items.length} entries found · {preview.data.items.filter(item => !item.importable).length} cannot be imported · {chosen} selected · room for {preview.data.remaining_capacity} more references in this project.</p>
      <div className="table-scroll mt16"><table><thead><tr><th scope="col">Import</th><th scope="col">Entry</th><th scope="col">Authors and year</th><th scope="col">Checks</th></tr></thead><tbody>{preview.data.items.map(item => <tr key={item.index}>
        <td><input type="checkbox" aria-label={`Import ${item.label}`} checked={item.importable && selected.has(item.index)} disabled={!item.importable || save.isSuccess} onChange={() => toggle(item.index)}/></td>
        <td><strong>{item.title || 'Untitled entry'}</strong><br/><span className="muted tiny">{item.label} · {item.kind}{item.container_title && ` · ${item.container_title}`}{item.doi && ` · ${item.doi}`}</span></td>
        <td>{item.authors.join('; ') || '—'}{item.year && ` (${item.year})`}</td>
        <td>{!item.errors.length && !item.warnings.length ? <span className="muted tiny">No issues found</span> : <ul className="tiny">{item.errors.map(text => <li key={text} className="alert">{text}</li>)}{item.warnings.map(text => <li key={text}>{text}</li>)}</ul>}</td>
      </tr>)}</tbody></table></div>
      {overCapacity && <p role="alert" className="alert mt16">Select at most {preview.data.remaining_capacity} entries; the project holds up to 500 references.</p>}
      {save.isError && <p role="alert" className="alert mt16">{save.error.message} You can retry the same import.</p>}
      {save.isSuccess ? <p role="status" className="notice mt16">Imported {save.data.items.length} references. Review them in the list below.</p>
        : <button className="btn primary mt16" disabled={!chosen || overCapacity || save.isPending} onClick={submitImport}>{save.isPending ? 'Importing…' : `Import ${chosen} selected`}</button>}
    </div>}
  </section>;
}
