import { useState, type FormEvent } from 'react';

const structures = {
  blank: [],
  article: ['Introduction', 'Literature review', 'Methodology', 'Results', 'Discussion', 'Conclusion'],
  review: ['Introduction', 'Review approach', 'Themes and findings', 'Research gaps', 'Discussion', 'Conclusion'],
} as const;

export function DraftStarter({ pending, error, onCreate, onCancel }: {
  pending: boolean; error?: string;
  onCreate: (input: { title: string; body: string }) => void; onCancel: () => void;
}) {
  const [title, setTitle] = useState('');
  const [structure, setStructure] = useState<keyof typeof structures>('blank');
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (title.trim() && !pending) onCreate({ title: title.trim(), body: structures[structure].map(heading => `# ${heading}\n\n`).join('') });
  }
  return <form className="card mt24" onSubmit={submit}><h2>Start a draft</h2><label className="field mt16">Draft name<input value={title} onChange={event => setTitle(event.target.value)} maxLength={180} required disabled={pending}/></label><label className="field mt16">Starting structure<select value={structure} onChange={event => setStructure(event.target.value as keyof typeof structures)} disabled={pending}><option value="blank">Blank draft</option><option value="article">Research article</option><option value="review">Literature review</option></select></label><p className="muted mt16">Structures add section headings only. Write and verify your own research content.</p>{error && <p role="alert" className="alert mt16">{error}</p>}<div className="row mt16"><button className="btn primary" type="submit" disabled={pending || !title.trim()}>{pending ? 'Creating…' : 'Create draft'}</button><button className="btn" type="button" disabled={pending} onClick={onCancel}>Cancel</button></div></form>;
}
