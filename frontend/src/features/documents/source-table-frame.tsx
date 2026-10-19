import { useRef, type ReactNode } from 'react';

export function SourceTableFrame({ columns, page, children }: { columns: number; page: number; children: ReactNode }) {
  const viewport = useRef<HTMLDivElement>(null);
  function move(direction: number) {
    const element = viewport.current;
    if (element) element.scrollBy({ left: direction * Math.max(160, element.clientWidth * 0.8), behavior: 'smooth' });
  }
  return <section className="source-table-frame">
    {columns > 3 && <div className="source-table-navigation">
      <p className="tiny muted">All {columns} columns are included. Scroll sideways to see the remaining columns, or use these controls. Focus the table and use the left/right arrow keys.</p>
      <div className="row gap8"><button className="btn" onClick={() => move(-1)} aria-label={`Scroll table on page ${page} left`}>← Previous columns</button><button className="btn" onClick={() => move(1)} aria-label={`Scroll table on page ${page} right`}>Next columns →</button></div>
    </div>}
    <div ref={viewport} className="library-table-scroll source-table" role="region" aria-label={`Source table on page ${page}, ${columns} columns`} tabIndex={0}>{children}</div>
  </section>;
}
