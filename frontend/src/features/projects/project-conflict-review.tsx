import type { Project } from './api';
import type { ProjectFormValues } from './schemas';

function Lines({ values }: { values: string[] }) {
  return values.length ? <ul>{values.map((value, index) => <li key={`${index}-${value}`}>{value}</li>)}</ul> : <p className="muted">None provided.</p>;
}

export function ProjectConflictReview({ latest, local, onKeepLocal, onUseLatest }: {
  latest: Project;
  local: ProjectFormValues;
  onKeepLocal: () => void;
  onUseLatest: () => void;
}) {
  return <section className="notice mt24" aria-labelledby="project-conflict-title">
    <div>
      <h2 id="project-conflict-title">This project changed while you were editing</h2>
      <p className="mt16">Compare your unsaved version with the latest saved version. Nothing has been overwritten.</p>
      <div className="project-form-grid mt16">
        <section aria-label="Your unsaved version"><h3>Your unsaved version</h3><p><strong>Title:</strong> {local.title || 'Not set'}</p><p><strong>Description:</strong> {local.description || 'Not set'}</p><p><strong>Research questions:</strong></p><Lines values={local.research_questions.split('\n').map(value => value.trim()).filter(Boolean)}/><p><strong>Objectives:</strong></p><Lines values={local.objectives.split('\n').map(value => value.trim()).filter(Boolean)}/></section>
        <section aria-label="Latest saved version"><h3>Latest saved version</h3><p><strong>Title:</strong> {latest.title}</p><p><strong>Description:</strong> {latest.description || 'Not set'}</p><p><strong>Research questions:</strong></p><Lines values={latest.research_questions}/><p><strong>Objectives:</strong></p><Lines values={latest.objectives}/></section>
      </div>
      <div className="row wrap mt16"><button className="btn primary" type="button" onClick={onKeepLocal}>Keep my edits</button><button className="btn" type="button" onClick={onUseLatest}>Load the latest saved version</button></div>
    </div>
  </section>;
}
