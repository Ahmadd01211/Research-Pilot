import { expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DraftStarter } from '../src/features/writing/draft-starter';

it('creates an explicitly named article with headings and no generated research claims', async () => {
  const create = vi.fn(), cancel = vi.fn();
  render(<DraftStarter pending={false} onCreate={create} onCancel={cancel}/>);
  const ui = userEvent.setup();
  expect(screen.getByRole('button', { name: 'Create draft' })).toBeDisabled();
  await ui.type(screen.getByLabelText('Draft name'), 'My article');
  await ui.selectOptions(screen.getByLabelText('Starting structure'), 'article');
  await ui.click(screen.getByRole('button', { name: 'Create draft' }));
  expect(create).toHaveBeenCalledWith({ title: 'My article', body: '# Introduction\n\n# Literature review\n\n# Methodology\n\n# Results\n\n# Discussion\n\n# Conclusion\n\n' });
});
it('keeps the selected template and title after a server error', async () => {
  const props = { pending: false, onCreate: vi.fn(), onCancel: vi.fn() };
  const { rerender } = render(<DraftStarter {...props}/>);
  const ui = userEvent.setup();
  await ui.type(screen.getByLabelText('Draft name'), 'Review');
  await ui.selectOptions(screen.getByLabelText('Starting structure'), 'review');
  rerender(<DraftStarter {...props} error="Try again"/>);
  expect(screen.getByLabelText('Draft name')).toHaveValue('Review');
  expect(screen.getByLabelText('Starting structure')).toHaveValue('review');
  expect(screen.getByRole('alert')).toHaveTextContent('Try again');
});
