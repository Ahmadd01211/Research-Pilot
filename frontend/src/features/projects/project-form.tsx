import { useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, CheckCircle2, LoaderCircle, Save } from 'lucide-react';
import { mutate } from '@/lib/api/client';
import { projectKey, type Project } from './api';
import { projectFields, projectFormSchema, type ProjectFormValues } from './schemas';
export function ProjectForm({ project }: { project?: Project }) {
  const navigate = useNavigate(), queryClient = useQueryClient(), [error, setError] = useState('');
  const initialRevision = useRef(project?.revision);
  const request = useRef<{ signature: string; id: string } | null>(null);
  const { register, handleSubmit, formState: { errors, isSubmitting, isDirty } } = useForm<ProjectFormValues>({ resolver: zodResolver(projectFormSchema), defaultValues: { title: project?.title || '', description: project?.description || '', research_questions: project?.research_questions.join('\n') || '', objectives: project?.objectives.join('\n') || '' } });
  async function submit(values: ProjectFormValues) {
    setError(''); const fields = projectFields(values);
    try {
      let result: Project;
      if (project) result = await mutate<Project>(`/projects/${project.id}`, 'PATCH', { ...fields, expected_revision: initialRevision.current });
      else { const signature = JSON.stringify(fields); if (!request.current || request.current.signature !== signature) request.current = { signature, id: crypto.randomUUID() }; result = await mutate<Project>('/projects', 'POST', { ...fields, request_id: request.current.id }); }
      queryClient.setQueryData(projectKey(result.id), result); await queryClient.invalidateQueries({ queryKey: ['projects'] }); navigate(`/projects/${result.id}`, { replace: true });
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Unable to save your project. Your edits remain here.'); }
  }
  return <><Link className="back-projects" to={project ? `/projects/${project.id}` : '/projects'}><ArrowLeft size={14}/>{project ? 'Back to project' : 'All projects'}</Link><p className="eyebrow mt24">{project ? 'REFINE YOUR RESEARCH' : 'A FOCUSED SPACE FOR YOUR NEXT QUESTION'}</p><h1>{project ? 'Edit your project' : 'Create a research project'}</h1><p className="page-subtitle">A clear question and purpose will guide the evidence you collect.</p><form className="card project-form" onSubmit={event => { void handleSubmit(submit)(event); }} noValidate><label className="field"><span>Project title</span><input aria-label="Project title" {...register('title')} maxLength={160} aria-invalid={!!errors.title} aria-describedby="title-error" placeholder="e.g. AI-supported learning in higher education"/><small id="title-error" className="field-error">{errors.title?.message}</small></label><label className="field"><span>Description</span><textarea aria-label="Description" {...register('description')} maxLength={4000} aria-invalid={!!errors.description} aria-describedby="description-error" placeholder="Describe the focus and boundaries of your research."/><small id="description-error" className="field-error">{errors.description?.message}</small></label><div className="project-form-grid"><label className="field"><span>Research questions</span><textarea aria-label="Research questions" {...register('research_questions')} aria-invalid={!!errors.research_questions} aria-describedby="questions-help" placeholder="What do you want to understand?"/><small id="questions-help" className={errors.research_questions ? 'field-error' : 'muted'}>{errors.research_questions?.message || 'One question per line. Up to 20; 500 characters each.'}</small></label><label className="field"><span>Research objectives</span><textarea aria-label="Research objectives" {...register('objectives')} aria-invalid={!!errors.objectives} aria-describedby="objectives-help" placeholder="What will this project aim to establish?"/><small id="objectives-help" className={errors.objectives ? 'field-error' : 'muted'}>{errors.objectives?.message || 'One objective per line. Up to 20; 500 characters each.'}</small></label></div>{error && <div role="alert" className="alert">{error}</div>}<div className="form-footer"><span className="muted tiny"><CheckCircle2 size={13}/> {isDirty ? 'Your changes have not been saved yet.' : 'Visible only to your account.'}</span><div className="row"><Link className="btn" to={project ? `/projects/${project.id}` : '/projects'}>Cancel</Link><button type="submit" className="btn primary" disabled={isSubmitting}>{isSubmitting ? <LoaderCircle size={16} className="spin"/> : <Save size={16}/>} {isSubmitting ? 'Saving…' : project ? 'Save changes' : 'Create project'}</button></div></div></form></>;
}
