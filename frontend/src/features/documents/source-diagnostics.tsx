import type { components } from '@/lib/api/schema';
type Quality=components['schemas']['PageQuality'];
type Summary=components['schemas']['DocumentQuality'];
type SourceLink=components['schemas']['SourceLink'];
const labels={checked:'Checks passed',needs_review:'Needs review',blocked:'Evidence withheld',not_assessed:'Not assessed'};
function allowedTarget(link:SourceLink):string|undefined {
  if(link.status!=='allowed'||!link.target)return;
  try { const url=new URL(link.target); if(['https:','http:'].includes(url.protocol)&&!url.username&&!url.password)return url.href;
    if(url.protocol==='mailto:'&&!url.search&&!url.hash&&!/[\r\n]/u.test(link.target))return url.href;
  } catch { /* Untrusted PDF destinations never become executable anchors. */ }
}
export function SourceDiagnostics({quality,summary,links=[],onPage,onLocate,error,onRetry}:{quality?:Quality|null;summary?:Summary;links?:SourceLink[];onPage:(page:number)=>void;onLocate:(id:string)=>void;error?:boolean;onRetry:()=>void}) {
  return <section className="notice mt16" aria-label="Automatic source assessment"><h3>Automatic source checks</h3>
    <p className="tiny muted mt16">Heuristic checks, not a guarantee of accuracy. Flagged content remains readable; affected evidence is withheld from retrieval. Linked websites are not fetched.</p>
    {summary?.pages && <><p className="mt16">Document: {summary.checked_pages} pages checked without flags · {summary.review_pages} need review · {summary.blocked_pages} withheld · {summary.not_assessed_pages} not assessed. {summary.link_count} source links retained.</p>
      {summary.pages.some(p=>p.state!=='checked')&&<details className="mt16"><summary>Review flagged or unassessed pages</summary>{summary.pages.filter(p=>p.state!=='checked').map(p=><div className="mt16" key={p.page_number}><button className="btn" onClick={()=>onPage(p.page_number)}>Page {p.page_number} · {labels[p.state]}</button>{(p.findings??[]).map(f=><p className="tiny" key={f.code}>{f.message}</p>)}</div>)}</details>}</>}
    {error&&<p role="alert" className="mt16">Document assessment is unavailable. <button className="btn" onClick={onRetry}>Retry assessment</button></p>}
    <p className="mt16"><strong>This page: {quality?labels[quality.state]:'Not assessed'}</strong></p>
    {!quality&&<p className="tiny muted">Update the reader to prepare current link and quality metadata.</p>}
    {quality?.findings.length ? <ul className="mt16">{quality.findings.map(f=><li key={f.code}>{f.message}</li>)}</ul>:quality&&<p className="tiny muted">These checks found no issue. Verify important claims against the original.</p>}
    <details className="mt16"><summary>Source links on this page ({links.length})</summary>
      {!links.length&&<p className="tiny mt16">No supported PDF link annotation, visible URL or DOI was detected.</p>}
      {links.map(link=>{const href=allowedTarget(link);return <div className="source-link-record mt16" key={link.id}><p>{link.text||'Link without readable label'}</p>{href?<a className="source-link-target" href={href} target="_blank" rel="noopener noreferrer" referrerPolicy="no-referrer">{link.target}</a>:link.status==='internal'&&link.target_page?<button className="btn" onClick={()=>onPage(link.target_page!)}>Open PDF page {link.target_page}</button>:<p className="tiny muted">{(link.status==='blocked'||link.target)?'Unsafe or unsupported link action disabled.':'Internal destination could not be resolved.'}</p>}<div className="mt16"><button className="btn" onClick={()=>onLocate(link.id)}>Show link location in PDF</button></div><p className="tiny muted">{link.origin.replaceAll('_',' ')} · {link.word_indices.length?'Measured text attached':'No measured text anchor'}</p></div>;})}
    </details></section>;
}
