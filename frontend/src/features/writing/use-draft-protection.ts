import { useState } from 'react';

export type DraftContent = { title: string; body: string; revision: number };

// Server refreshes must never replace a researcher's in-progress text.
export function useDraftProtection(initial: DraftContent) {
  const [baseline, setBaseline] = useState(initial);
  const [title, setTitle] = useState(initial.title);
  const [body, setBody] = useState(initial.body);
  const dirty = title !== baseline.title || body !== baseline.body;
  function acceptSaved(saved: DraftContent, submitted: DraftContent) {
    setBaseline(saved);
    setTitle(current => current === submitted.title ? saved.title : current);
    setBody(current => current === submitted.body ? saved.body : current);
  }
  function loadLatest(latest: DraftContent) {
    setBaseline(latest);
    setTitle(latest.title);
    setBody(latest.body);
  }
  return { title, setTitle, body, setBody, baseline, dirty, acceptSaved, loadLatest, reapplyTo: setBaseline };
}
