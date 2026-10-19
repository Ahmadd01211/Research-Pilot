import { expect,it,vi } from 'vitest';
import { render,screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SourceDiagnostics } from '../src/features/documents/source-diagnostics';
const base={id:'link-one',box:[.1,.2,.3,.4] as [number,number,number,number],text:'Dataset',word_indices:[0],source_ids:['passage'],origin:'annotation' as const,target_page:null};
it('opens only supported destinations and provides a source-location action',async()=>{
  const locate=vi.fn();render(<SourceDiagnostics links={[{...base,status:'allowed',target:'https://example.org/data'}]} onPage={vi.fn()} onLocate={locate} onRetry={vi.fn()}/>);
  const user=userEvent.setup();await user.click(screen.getByText('Source links on this page (1)'));
  const anchor=screen.getByRole('link',{name:'https://example.org/data'});
  expect(anchor).toHaveAttribute('rel','noopener noreferrer');expect(anchor).toHaveAttribute('referrerpolicy','no-referrer');
  await user.click(screen.getByRole('button',{name:'Show link location in PDF'}));expect(locate).toHaveBeenCalledWith('link-one');
});
it('never turns PDF scripts into clickable links even if a response incorrectly says allowed',async()=>{
  render(<SourceDiagnostics links={[{...base,status:'allowed',target:'javascript:alert(1)'}]} onPage={vi.fn()} onLocate={vi.fn()} onRetry={vi.fn()}/>);
  await userEvent.setup().click(screen.getByText('Source links on this page (1)'));
  expect(screen.queryByRole('link')).not.toBeInTheDocument();
});
it('navigates internal destinations without loading an external website',async()=>{
  const page=vi.fn();render(<SourceDiagnostics links={[{...base,status:'internal',target:null,target_page:2}]} onPage={page} onLocate={vi.fn()} onRetry={vi.fn()}/>);
  const user=userEvent.setup();await user.click(screen.getByText('Source links on this page (1)'));
  await user.click(screen.getByRole('button',{name:'Open PDF page 2'}));expect(page).toHaveBeenCalledWith(2);
});
it('reports an unassessed legacy extraction honestly',()=>{
  render(<SourceDiagnostics onPage={vi.fn()} onLocate={vi.fn()} onRetry={vi.fn()}/>);
  expect(screen.getByText('This page: Not assessed')).toBeVisible();
  expect(screen.getByText(/not a guarantee of accuracy/)).toBeVisible();
});
