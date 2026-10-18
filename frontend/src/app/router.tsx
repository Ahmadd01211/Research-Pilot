import { Navigate, Route, Routes, Link, Outlet, useLocation, useSearchParams } from 'react-router';
import { ArrowRight, BookOpen, CheckCircle2, FileText, LayoutDashboard, LoaderCircle, ShieldCheck, UserRound } from 'lucide-react';
import { Brand } from '@/components/shared/brand';
import { AuthLayout } from '@/features/auth/auth-layout';
import { LoginForm, RegisterForm } from '@/features/auth/auth-form';
import { ProfileForm } from '@/features/auth/profile-form';
import { useSession } from '@/features/auth/use-session';

function LoginPage() {
  const [params] = useSearchParams();
  return <div>{params.get('registered') === '1' && <p role="status" className="notice registration-notice"><CheckCircle2 size={16}/>Account created. Sign in to continue.</p>}<LoginForm/></div>;
}
function ProtectedLayout() {
  const session = useSession(), location = useLocation();
  if (session.isPending) return <main className="center"><p role="status" className="row"><LoaderCircle className="spin" size={20}/>Opening your workspace…</p></main>;
  if (session.isError) return <main className="center"><section className="card"><h1>Your account service is unavailable.</h1><p className="muted">We couldn’t confirm your session. Your data has not been cleared.</p><button className="btn primary mt24" onClick={() => void session.refetch()}>Try again</button></section></main>;
  if (!session.data) return <Navigate to="/login" replace/>;
  return <div className="workspace"><a className="skip-link" href="#workspace-main">Skip to content</a><aside className="sidebar"><Brand/><div className="workspace-label"><span className="avatar"><UserRound size={16}/></span><div><strong>Personal workspace</strong><small>Research, connected.</small></div></div><p className="nav-label">WORKSPACE</p><nav aria-label="Main navigation"><Link to="/dashboard" aria-current={location.pathname === '/dashboard' ? 'page' : undefined}><LayoutDashboard size={18}/>Dashboard</Link><Link to="/profile" aria-current={location.pathname === '/profile' ? 'page' : undefined}><UserRound size={18}/>Account settings</Link></nav><div className="sidebar-note"><ShieldCheck size={19}/><strong>Evidence comes first.</strong><p>We’re building the research workflow one complete, tested feature at a time.</p></div><div className="sidebar-user"><span className="avatar">{session.data.display_name[0]}</span><div><strong>{session.data.display_name}</strong><small>{session.data.email}</small></div></div></aside><div className="workspace-area"><header className="topbar"><span className="muted">Personal workspace <span className="crumb-slash">/</span><strong>{location.pathname === '/profile' ? 'Account settings' : 'Dashboard'}</strong></span><span className="badge"><ShieldCheck size={13}/>Authenticated</span></header><main id="workspace-main" className="workspace-main" tabIndex={-1}><Outlet/></main></div></div>;
}
function Dashboard() {
  const { data: user } = useSession();
  return <><p className="eyebrow">YOUR RESEARCH, CONNECTED</p><h1>Welcome, {user?.display_name.split(' ')[0]}.</h1><p className="page-subtitle">Your account is ready. A thoughtful research workspace starts here.</p><section className="welcome-card"><div className="welcome-icon"><BookOpen size={29}/></div><div><h2>Build on a secure foundation.</h2><p>Your account and profile are connected to the backend. Projects, papers, and evidence tools are the next implementation steps.</p></div><Link className="btn primary" to="/profile">Manage your profile<ArrowRight size={16}/></Link></section><div className="dashboard-grid"><section className="card"><div className="card-heading"><h2>Your first research project</h2><p className="muted">The next vertical feature will give your question a home.</p></div><div className="empty-content"><FileText size={30}/><h3>Project management is coming next.</h3><p>No sample projects or invented research statistics appear in this live account view.</p></div></section><section className="card principles"><p className="eyebrow">HOW WE ARE BUILDING</p><h2>A clear path from evidence to writing.</h2><ol><li><span>01</span>Research projects & private document library</li><li><span>02</span>Source-grounded chat & literature analysis</li><li><span>03</span>Academic writing, references & exports</li></ol></section></div></>;
}
function ProfilePage() {
  const { data: user } = useSession();
  return <><p className="eyebrow">ACCOUNT SETTINGS</p><h1>Your profile</h1><p className="page-subtitle">Manage the name associated with your research account.</p>{user && <ProfileForm user={user}/>}</>;
}
function Home() {
  return <div className="landing"><header><Brand/><div className="row"><Link to="/login" className="btn">Sign in</Link><Link to="/register" className="btn primary">Create account<ArrowRight size={16}/></Link></div></header><main><p className="eyebrow">A CALMER SPACE FOR SERIOUS RESEARCH</p><h1>Your research is connected.<br/>Your thinking should be, <span>too.</span></h1><p>ResearchPilot is being built to connect academic papers, traceable evidence, and considered writing. Start with your personal account.</p><div className="row hero-actions"><Link className="btn primary" to="/register">Create your research account<ArrowRight size={16}/></Link><Link className="btn" to="/dashboard">Open workspace</Link></div><div className="landing-note"><ShieldCheck size={16}/><span>Foundation release: secure accounts and profiles. Research tools are under development.</span></div></main><footer>ResearchPilot · Researcher-led. Evidence-first.</footer></div>;
}
export function AppRoutes() {
  return <Routes><Route path="/" element={<Home/>}/><Route element={<AuthLayout/>}><Route path="login" element={<LoginPage/>}/><Route path="register" element={<RegisterForm/>}/></Route><Route element={<ProtectedLayout/>}><Route path="dashboard" element={<Dashboard/>}/><Route path="profile" element={<ProfilePage/>}/></Route><Route path="*" element={<main className="center"><section className="card"><h1>Page not found.</h1><p className="muted">This feature is not available yet.</p><Link className="btn primary" to="/">Return home</Link></section></main>}/></Routes>;
}
