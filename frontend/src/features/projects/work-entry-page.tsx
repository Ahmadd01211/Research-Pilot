import { Link, Navigate } from 'react-router';
import { ArrowRight, FileSearch, LoaderCircle, PenLine, Plus } from 'lucide-react';
import { useProjects } from './api';

type Task = 'evidence' | 'writing';

export function WorkEntryPage({ task }: { task: Task }) {
  const projects = useProjects('active', '', 12);
  const items = projects.data?.pages.flatMap(page => page.items) ?? [];
  const total = projects.data?.pages[0]?.total ?? 0;
  const title = task === 'evidence' ? 'Find evidence' : 'Continue writing';
  const description = task === 'evidence'
    ? 'Choose the research project whose papers you want to search.'
    : 'Choose the research project whose draft you want to open.';

  if (projects.isPending) return <div className="card project-empty" role="status"><LoaderCircle className="spin"/>Loading your projects…</div>;
  if (projects.isError) return <div className="card project-empty" role="alert"><h1>Projects could not be loaded</h1><button className="btn" onClick={() => void projects.refetch()}>Try again</button></div>;
  if (total === 1 && items[0]) return <Navigate to={`/projects/${items[0].id}/${task}`} replace/>;

  return <><div className="page-heading"><div><p className="eyebrow">YOUR WORKSPACE</p><h1>{title}</h1><p className="page-subtitle">{description}</p></div></div>
    {total === 0 ? <section className="card project-empty"><h2>Start with a research project</h2><p className="muted">Create a project to keep your sources and writing together.</p><Link className="btn primary" to="/projects/new"><Plus size={16}/>Create project</Link></section> : <><div className="project-choice-list">{items.map(project => <Link className="card project-choice" key={project.id} to={`/projects/${project.id}/${task}`}><span className="project-choice-icon">{task === 'evidence' ? <FileSearch size={20}/> : <PenLine size={20}/>}</span><span><strong>{project.title}</strong><small>{project.description || 'Open this research project'}</small></span><ArrowRight size={17}/></Link>)}</div>{projects.hasNextPage && <div className="load-more"><button className="btn" onClick={() => void projects.fetchNextPage()} disabled={projects.isFetchingNextPage}>{projects.isFetchingNextPage ? 'Loading…' : 'Show more projects'}</button></div>}<p className="muted mt24">Looking for an archived project? <Link to="/projects?status=archived">View archived projects</Link>.</p></>}
  </>;
}
