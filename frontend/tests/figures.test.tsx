import { expect,it,vi } from 'vitest';
import { render,screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { FigureCard } from '../src/features/documents/figure-card';
vi.mock('../src/features/documents/pdf-canvas',()=>({default:({crop,page}:{crop?:number[];page:number})=><div role="img" aria-label={crop?`Figure crop on page ${page}`:`Full source page ${page}`}/>}));
const figure={id:'figure-id',label:'Figure 1',caption:'FIGURE 1 Survey results.',caption_word_indices:[0],box:[.1,.1,.9,.4] as [number,number,number,number],detection:'embedded_image' as const,related_passages:[{page_number:2,passage_id:'discussion-id',text:'The authors explicitly refer to Figure 1 here.'}]};
function open(item=figure){const show=vi.fn();render(<MemoryRouter><FigureCard figure={item} page={9} base="/projects/p/documents/d" sourceHash="source-hash" reader="reader-v5" selected onShow={show}/></MemoryRouter>);return show;}
it('shows a source caption and renders a crop only on request',async()=>{
  const show=open();const ui=userEvent.setup();
  expect(screen.getByText(figure.caption)).toBeVisible();
  expect(screen.queryByRole('img')).not.toBeInTheDocument();
  await ui.click(screen.getByRole('button',{name:'Preview figure'}));
  expect(await screen.findByRole('img',{name:'Figure crop on page 9'})).toBeVisible();
  expect(show).toHaveBeenCalled();
  expect(screen.getByText(/No AI image interpretation/)).toBeVisible();
});
it('uses an explicit full-page fallback without inventing chart descriptions',async()=>{
  const item={...figure,box:null,caption:null,caption_word_indices:[],detection:'source_page',label:'Visual evidence on PDF page 9',related_passages:[]} as unknown as typeof figure;
  open(item);const ui=userEvent.setup();
  expect(screen.getByText(/no title or description has been invented/)).toBeVisible();
  await ui.click(screen.getByRole('button',{name:'Preview source page'}));
  expect(await screen.findByRole('img',{name:'Full source page 9'})).toBeVisible();
});
it('links only the supplied source discussion with its source identity',async()=>{
  open();const ui=userEvent.setup();
  await ui.click(screen.getByText('Source text explicitly referencing this figure'));
  expect(screen.getByText(figure.related_passages[0].text)).toBeVisible();
  expect(screen.getByRole('link',{name:'Open source passage · Page 2'})).toHaveAttribute('href','/?page=2&passage=discussion-id&source=source-hash&reader=reader-v5');
});
