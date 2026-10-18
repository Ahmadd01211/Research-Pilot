import { Link } from 'react-router';
import { ArrowUpRight, FolderOpen, MessageCircle, Target } from 'lucide-react';
import type { Project } from './api';
export function ProjectCard({ project }: { project: Project }) {
  return <Link className="card project-card" to={`/projects/${project.id}`}><div className="project-card-top"><span className="project-symbol"><FolderOpen size={21}/></span><span className={`badge ${project.archived_at ? 'archived' : ''}`}>{project.archived_at ? 'Archived' : 'Active'}</span></div><h2>{project.title}</h2><p>{project.description || 'A focused space for your research questions, objectives, and evidence.'}</p><div className="project-card-meta"><span><MessageCircle size={13}/>{project.research_questions.length} questions</span><span><Target size={13}/>{project.objectives.length} objectives</span><ArrowUpRight size={15}/></div></Link>;
}
