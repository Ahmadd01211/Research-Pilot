import { expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SourceTableFrame } from '../src/features/documents/source-table-frame';

it('makes all seven columns discoverable and scrolls the actual table viewport', async () => {
  render(<SourceTableFrame columns={7} page={18}><table><tbody><tr>{Array.from({length:7},(_,i)=><td key={i}>Column {i+1}</td>)}</tr></tbody></table></SourceTableFrame>);
  const region=screen.getByRole('region',{name:'Source table on page 18, 7 columns'});
  const scroll=vi.fn();region.scrollBy=scroll;
  Object.defineProperty(region,'clientWidth',{value:400});
  expect(region).toHaveAttribute('tabindex','0');
  expect(screen.getByText(/All 7 columns are included/)).toBeVisible();
  expect(screen.getByRole('cell',{name:'Column 7'})).toBeInTheDocument();
  const user=userEvent.setup();
  await user.click(screen.getByRole('button',{name:'Scroll table on page 18 right'}));
  expect(scroll).toHaveBeenLastCalledWith({left:320,behavior:'smooth'});
  await user.click(screen.getByRole('button',{name:'Scroll table on page 18 left'}));
  expect(scroll).toHaveBeenLastCalledWith({left:-320,behavior:'smooth'});
});

it('keeps narrow tables keyboard accessible without extra navigation controls',()=>{
  render(<SourceTableFrame columns={2} page={8}><table><tbody><tr><td>Definition</td></tr></tbody></table></SourceTableFrame>);
  expect(screen.getByRole('region',{name:'Source table on page 8, 2 columns'})).toHaveAttribute('tabindex','0');
  expect(screen.queryByRole('button')).not.toBeInTheDocument();
});
