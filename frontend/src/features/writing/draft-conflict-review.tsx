import type { DraftContent } from './use-draft-protection';

type Props = {
  latest: DraftContent;
  title: string;
  body: string;
  onKeepMine: () => void;
  onLoadLatest: () => void;
};

export function DraftConflictReview({ latest, title, body, onKeepMine, onLoadLatest }: Props) {
  return <section className="card mt24" aria-label="Review conflicting draft versions"><h2>Review before saving</h2><p className="muted mt16">Another save changed this draft. Compare both versions, then choose which text to keep in the editor. Your choice does not save or overwrite the server version.</p><div className="draft-comparison mt16"><div><h3>Your unsaved text</h3><h4>{title}</h4><pre>{body}</pre></div><div><h3>Latest saved · version {latest.revision}</h3><h4>{latest.title}</h4><pre>{latest.body}</pre></div></div><div className="row wrap mt16"><button className="btn" type="button" onClick={onKeepMine}>Keep my text for editing</button><button className="btn" type="button" onClick={onLoadLatest}>Use latest saved text</button></div></section>;
}
