import { Link } from 'react-router';
import { BookOpen } from 'lucide-react';
export function Brand() {
  return <Link to="/" className="brand" aria-label="ResearchPilot home"><span className="brand-mark"><BookOpen size={23} strokeWidth={1.8}/></span><span>ResearchPilot<span className="brand-dot">.</span><small>ACADEMIC RESEARCH WORKSPACE</small></span></Link>;
}
