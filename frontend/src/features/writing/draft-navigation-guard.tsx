import { useBeforeUnload, useBlocker } from 'react-router';
import { useCallback, useEffect, useRef } from 'react';

export function DraftNavigationGuard({ dirty }: { dirty: boolean }) {
  const blocker = useBlocker(dirty);
  const stay = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (blocker.state !== 'blocked') return;
    const previous = document.activeElement as HTMLElement | null;
    stay.current?.focus();
    return () => previous?.focus();
  }, [blocker.state]);
  useBeforeUnload(useCallback((event: BeforeUnloadEvent) => {
    if (dirty) { event.preventDefault(); event.returnValue = ''; }
  }, [dirty]));
  if (blocker.state !== 'blocked') return null;
  return <section className="card draft-leave-prompt" role="alertdialog" aria-modal="true" aria-labelledby="draft-leave-title" onKeyDown={event => {
    if (event.key === 'Escape') { event.preventDefault(); blocker.reset(); }
    if (event.key === 'Tab') {
      const buttons = event.currentTarget.querySelectorAll('button');
      const first = buttons[0], last = buttons[buttons.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    }
  }}><h2 id="draft-leave-title">Leave without saving?</h2><p className="mt16">Your draft has unsaved changes. Stay to save your work, or discard these edits and leave.</p><div className="row wrap mt16"><button className="btn primary" ref={stay} onClick={() => blocker.reset()}>Keep editing</button><button className="btn danger" onClick={() => blocker.proceed()}>Discard edits and leave</button></div></section>;
}
