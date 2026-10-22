import { Navigate, Route, Routes, Link, Outlet, useLocation, useSearchParams } from 'react-router';
import { ArrowRight, CheckCircle2, FolderOpen, LayoutDashboard, LoaderCircle, ShieldCheck, UserRound } from 'lucide-react';
import { Brand } from '@/components/shared/brand';
import { AuthLayout } from '@/features/auth/auth-layout';
import { LoginForm, RegisterForm } from '@/features/auth/auth-form';
import { ProfileForm } from '@/features/auth/profile-form';
import { useSession } from '@/features/auth/use-session';
import { Dashboard } from '@/features/projects/dashboard';
import { ProjectListPage } from '@/features/projects/project-list-page';
import { ProjectDetailPage, ProjectEditPage } from '@/features/projects/project-detail-page';
import { ProjectForm } from '@/features/projects/project-form';
import { LibraryPage } from '@/features/documents/library-page';
import { DocumentPage } from '@/features/documents/document-page';
import { EvidenceSearchPage } from '@/features/documents/evidence-search-page';
import { MatrixPage } from '@/features/matrix/matrix-page';
import { GapsPage } from '@/features/gaps/gaps-page';
import { ReferencesPage } from '@/features/references/references-page';
import { WritingPage } from '@/features/writing/writing-page';
import { ExportsPage } from '@/features/exports/exports-page';

function LoginPage() {
  const [params] = useSearchParams();
  return <div>{params.get('registered') === '1' && <p role="status" className="notice registration-notice"><CheckCircle2 size={16}/>Account created. Sign in to continue.</p>}<LoginForm/></div>;
}
function ProtectedLayout() {
  const session = useSession(), location = useLocation();
  if (session.isPending) return <main className="center"><p role="status" className="row"><LoaderCircle className="spin" size={20}/>Opening your workspace…</p></main>;
  if (session.isError) return <main className="center"><section className="card"><h1>Your account service is unavailable.</h1><p className="muted">We couldn’t confirm your session. Your data has not been cleared.</p><button className="btn primary mt24" onClick={() => void session.refetch()}>Try again</button></section></main>;
  if (!session.data) return <Navigate to="/login" replace/>;
  return <div className="workspace"><a className="skip-link" href="#workspace-main">Skip to content</a><aside className="sidebar"><Brand/><div className="workspace-label"><span className="avatar"><UserRound size={16}/></span><div><strong>Personal workspace</strong><small>Research, connected.</small></div></div><p className="nav-label">WORKSPACE</p><nav aria-label="Main navigation"><Link to="/dashboard" aria-current={location.pathname === '/dashboard' ? 'page' : undefined}><LayoutDashboard size={18}/>Dashboard</Link><Link to="/projects" aria-current={location.pathname.startsWith('/projects') ? 'page' : undefined}><FolderOpen size={18}/>Research projects</Link><Link to="/profile" aria-current={location.pathname === '/profile' ? 'page' : undefined}><UserRound size={18}/>Account settings</Link></nav><div className="sidebar-note"><ShieldCheck size={19}/><strong>Evidence comes first.</strong><p>We’re building the research workflow one complete, tested feature at a time.</p></div><div className="sidebar-user"><span className="avatar">{session.data.display_name[0]}</span><div><strong>{session.data.display_name}</strong><small>{session.data.email}</small></div></div></aside><div className="workspace-area"><header className="topbar"><span className="muted">Personal workspace <span className="crumb-slash">/</span><strong>{location.pathname === '/profile' ? 'Account settings' : location.pathname.startsWith('/projects') ? 'Research projects' : 'Dashboard'}</strong></span><span className="badge"><ShieldCheck size={13}/>Authenticated</span></header><main id="workspace-main" className="workspace-main" tabIndex={-1}><Outlet/></main></div></div>;
}
function ProfilePage() {
  const { data: user } = useSession();
  return <><p className="eyebrow">ACCOUNT SETTINGS</p><h1>Your profile</h1><p className="page-subtitle">Manage the name associated with your research account.</p>{user && <ProfileForm user={user}/>}</>;
}
function Home() {
  return <div className="landing"><header><Brand/><div className="row"><Link to="/login" className="btn">Sign in</Link><Link to="/register" className="btn primary">Create account<ArrowRight size={16}/></Link></div></header><main><p className="eyebrow">A CALMER SPACE FOR SERIOUS RESEARCH</p><h1>Your research is connected.<br/>Your thinking should be, <span>too.</span></h1><p>ResearchPilot is being built to connect academic papers, traceable evidence, and considered writing. Start with your personal account.</p><div className="row hero-actions"><Link className="btn primary" to="/register">Create your research account<ArrowRight size={16}/></Link><Link className="btn" to="/dashboard">Open workspace</Link></div><div className="landing-note"><ShieldCheck size={16}/><span>Foundation release: secure accounts and profiles. Research tools are under development.</span></div></main><footer>ResearchPilot · Researcher-led. Evidence-first.</footer></div>;
}
export function AppRoutes() {
  return <Routes><Route path="/" element={<Home/>}/><Route element={<AuthLayout/>}><Route path="login" element={<LoginPage/>}/><Route path="register" element={<RegisterForm/>}/></Route><Route element={<ProtectedLayout/>}><Route path="dashboard" element={<Dashboard/>}/><Route path="profile" element={<ProfilePage/>}/><Route path="projects" element={<ProjectListPage/>}/><Route path="projects/new" element={<ProjectForm/>}/><Route path="projects/:id" element={<ProjectDetailPage/>}/><Route path="projects/:id/evidence" element={<EvidenceSearchPage/>}/><Route path="projects/:id/chat" element={<EvidenceSearchPage/>}/><Route path="projects/:id/matrix" element={<MatrixPage/>}/><Route path="projects/:id/gaps" element={<GapsPage/>}/><Route path="projects/:id/references" element={<ReferencesPage/>}/><Route path="projects/:id/writing" element={<WritingPage/>}/><Route path="projects/:id/writing/:draftId" element={<WritingPage/>}/><Route path="projects/:id/exports" element={<ExportsPage/>}/><Route path="projects/:id/library/:documentId" element={<DocumentPage/>}/><Route path="projects/:id/library" element={<LibraryPage/>}/><Route path="projects/:id/edit" element={<ProjectEditPage/>}/></Route><Route path="*" element={<main className="center"><section className="card"><h1>Page not found.</h1><p className="muted">This feature is not available yet.</p><Link className="btn primary" to="/">Return home</Link></section></main>}/></Routes>;
}
