import { act, renderHook } from '@testing-library/react';
import { expect, it } from 'vitest';
import { useDraftProtection } from '../src/features/writing/use-draft-protection';
it('preserves typing after submission while adopting the saved revision', () => {
  const { result } = renderHook(() => useDraftProtection({ title: 'Draft', body: 'First', revision: 1 }));
  act(() => result.current.setBody('Submitted'));
  const submitted = { title: result.current.title, body: result.current.body, revision: 1 };
  act(() => result.current.setBody('Submitted plus newer edits'));
  act(() => result.current.acceptSaved({ title: 'Draft', body: 'Submitted', revision: 2 }, submitted));
  expect(result.current.body).toBe('Submitted plus newer edits');
  expect(result.current.baseline.revision).toBe(2);
  expect(result.current.dirty).toBe(true);
});
