import { afterEach, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppRoutes } from '../src/app/router';
vi.mock('../src/features/documents/pdf-canvas', () => ({ default: ({ page, boxes }: {page:number;boxes:unknown[]}) => <div role="img" data-boxes={JSON.stringify(boxes)} aria-label={`PDF page ${page}, ${boxes.length} highlighted words`}/> }));
const p='11111111-1111-4111-8111-111111111111', d='22222222-2222-4222-8222-222222222222';
const layout={ version:'reader-v2', width:612,height:792,rotation:0,words:[{text:'Measured',box:[.1,.1,.2,.12],margin:false},{text:'evidence.',box:[.21,.1,.4,.12],margin:false}],passages:[{id:'anchor-one',text:'Measured evidence.',word_indices:[0,1]}],excluded_margin_text:[] };
afterEach(()=>vi.unstubAllGlobals());
function open(options: {legacy?:boolean;query?:string;table?:boolean;figure?:boolean;fallback?:boolean;formula?:boolean;captionTable?:boolean;subcolumns?:boolean}={}) {
  const mock=vi.fn((url:string, init?:RequestInit)=>{
    if(url==='/api/v1/me')return Promise.resolve(Response.json({display_name:'Researcher',email:'r@example.com'}));
    if(url==='/api/v1/auth/csrf')return Promise.resolve(Response.json({csrf_token:'synthetic'}));
    if(init?.method==='POST')return Promise.resolve(Response.json({status:'queued'}));
    if(url.includes('/pages/'))return Promise.resolve(Response.json({document_id:d,page_number:1,text:'Raw    source\nline.',source_sha256:'source-one',extractor_version:'extractor-v2',layout:options.legacy?null:options.subcolumns?{...layout,passages:[],words:[{text:'City',box:[.1,.2,.2,.22],margin:false},{text:'7.4',box:[.4,.2,.45,.22],margin:false},{text:'5',box:[.5,.2,.55,.22],margin:false},{text:'4',box:[.6,.2,.65,.22],margin:false},{text:'37',box:[.7,.2,.75,.22],margin:false}],tables:[{box:[.1,.1,.9,.5],detection:'numbered-model-subcolumns',rows:[['Location','Firm Share','Firm Rank','Employment Share','Employment Rank'].map((text,i)=>({id:'head-'+i,text,word_indices:[]})),['City','7.4','5','4','37'].map((text,i)=>({id:'value-'+i,text,word_indices:[i]}))]}]}:options.formula?{...layout,words:[{text:'g',box:[.43,.12,.44,.14],margin:false},{text:'=',box:[.45,.12,.46,.14],margin:false},{text:'\uf0da',box:[.48,.18,.50,.20],margin:false}],passages:[{id:'equation',text:'g = \uf0da',word_indices:[0,1,2]}]}:options.figure?{...layout,figures:[{id:'figure-one',label:'Figure 1',caption:'Measured evidence.',caption_word_indices:[0,1],box:options.fallback?null:[.1,.2,.8,.5],detection:options.fallback?'source_page':'embedded_image',related_passages:[]}]}:options.table || options.captionTable?{...layout,passages:options.captionTable?layout.passages:[],tables:[{box:[.1,.1,.9,.5],detection:"measured",rows:[[{...layout.passages[0],id:"cell-a",text:"Machine learning"},{...layout.passages[0],id:"cell-b",word_indices:options.captionTable?[1]:[0,1],text:"Algorithms that improve with data"}]]}]}:layout}));
    if(url.includes('/documents/'))return Promise.resolve(Response.json({id:d,filename:'Academic paper.pdf',status:'extracted',processing:{page_count:2}}));
    return Promise.resolve(Response.json({id:p,archived_at:null}));
  });
  vi.stubGlobal('fetch',mock);
  const cache=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});
  render(<QueryClientProvider client={cache}><MemoryRouter initialEntries={[`/projects/${p}/library/${d}${options.query??''}`]}><AppRoutes/></MemoryRouter></QueryClientProvider>);
  return mock;
}
it('shows readable passages and highlights measured word boxes in the original',async()=>{
  open();const ui=userEvent.setup();
  expect(await screen.findByText('Measured evidence.')).toBeVisible();
  await ui.click(screen.getByRole('button',{name:'Show passage 1 in PDF'}));
  expect(await screen.findByRole('img',{name:'PDF page 1, 2 highlighted words'})).toBeVisible();
  await ui.click(screen.getByRole('button',{name:'Raw'}));
  expect(screen.getByLabelText('Extracted text for page 1')).toHaveTextContent('Raw source line.');
});
it('opens a source-versioned citation link at its saved passage',async()=>{
  open({query:'?page=1&passage=anchor-one&source=source-one&reader=reader-v2'});
  expect(await screen.findByRole('img',{name:'PDF page 1, 2 highlighted words'})).toBeVisible();
});
it('never highlights a citation whose source identity does not match',async()=>{
  open({query:'?page=1&passage=anchor-one&source=another-file&reader=reader-v2'});
  expect(await screen.findByRole('alert')).toHaveTextContent('highlight has been disabled');
  expect(screen.getByRole('img',{name:'PDF page 1, 0 highlighted words'})).toBeVisible();
});
it('lets a user request bounded reader preparation for a legacy extraction',async()=>{
  const mock=open({legacy:true});const ui=userEvent.setup();
  await ui.click(await screen.findByRole('button',{name:'Prepare readable text and highlights'}));
  expect(await screen.findByText(/Extraction has not completed/)).toBeVisible();
  const call=mock.mock.calls.find(([,init])=>init?.method==='POST');
  expect(call?.[0]).toBe(`/api/v1/projects/${p}/documents/${d}/prepare-reader`);
  expect(call?.[1]?.headers).toMatchObject({'x-csrf-token':'synthetic'});
});
it('provides a text-only layout for narrow screens and reading preferences',async()=>{
  open();const ui=userEvent.setup();
  await screen.findByText('Measured evidence.');
  await ui.selectOptions(screen.getByLabelText('Reader layout'),'text');
  expect(screen.queryByRole('img')).not.toBeInTheDocument();
  expect(screen.getByText('Measured evidence.')).toBeVisible();
});

it('does not substitute page one for an invalid citation page',async()=>{
  open({query:'?page=999&source=source-one'});
  expect(await screen.findByRole('heading',{name:'Source page unavailable'})).toBeVisible();
  expect(screen.queryByRole('img')).not.toBeInTheDocument();
});
it('disables an unknown passage anchor rather than selecting another passage',async()=>{
  open({query:'?page=1&passage=nonexistent&source=source-one&reader=reader-v2'});
  expect(await screen.findByRole('alert')).toHaveTextContent('highlight has been disabled');
  expect(screen.getByRole('img',{name:'PDF page 1, 0 highlighted words'})).toBeVisible();
});

it('renders detected table rows as cells with source highlights',async()=>{
  open({table:true});const ui=userEvent.setup();
  expect(await screen.findByRole('rowheader',{name:/Machine learning/})).toBeVisible();
  expect(screen.getByRole('cell',{name:/Algorithms that improve with data/})).toBeVisible();
  await ui.click(screen.getByRole('button',{name:'Show row 1, column 2 in PDF'}));
  expect(await screen.findByRole('img',{name:'PDF page 1, 2 highlighted words'})).toBeVisible();
});

it('highlights only the image region when viewing a figure',async()=>{
  open({figure:true});const ui=userEvent.setup();
  await ui.click(await screen.findByRole('button',{name:'View Figure 1 in PDF'}));
  expect(await screen.findByRole('img',{name:'PDF page 1, 1 highlighted words'})).toBeVisible();
});
it('does not substitute caption highlights for an uncertain figure boundary',async()=>{
  open({figure:true,fallback:true,query:'?page=1&figure=figure-one&source=source-one&reader=reader-v2'});
  expect(await screen.findByRole('button',{name:'Open source page'})).toBeVisible();
  expect(await screen.findByRole('img',{name:'PDF page 1, 0 highlighted words'})).toBeVisible();
});
it('disables figure and caption highlights for a mismatched source',async()=>{
  open({figure:true,query:'?page=1&figure=figure-one&source=wrong-source&reader=reader-v2'});
  expect(await screen.findByRole('alert')).toHaveTextContent('highlight has been disabled');
  expect(screen.getByRole('img',{name:'PDF page 1, 0 highlighted words'})).toBeVisible();
});

it('switches exclusively between caption text and image highlights',async()=>{
  open({figure:true});const ui=userEvent.setup();
  await ui.click(await screen.findByRole('button',{name:'View Figure 1 in PDF'}));
  expect(await screen.findByRole('img',{name:'PDF page 1, 1 highlighted words'})).toBeVisible();
  await ui.click(screen.getByRole('button',{name:'View caption in PDF'}));
  expect(await screen.findByRole('img',{name:'PDF page 1, 2 highlighted words'})).toBeVisible();
  await ui.click(screen.getByRole('button',{name:'Show passage 1 in PDF'}));
  expect(screen.getByRole('img',{name:'PDF page 1, 2 highlighted words'})).toBeVisible();
});
it('can highlight caption text independently on a full-page fallback',async()=>{
  open({figure:true,fallback:true,query:'?page=1&caption=figure-one&source=source-one&reader=reader-v2'});
  expect(await screen.findByRole('img',{name:'PDF page 1, 2 highlighted words'})).toBeVisible();
});

it('never paints an undecodable equation glyph box over the following paragraph',async()=>{
  open({formula:true});const ui=userEvent.setup();
  await ui.click(await screen.findByRole('button',{name:'Show passage 1 in PDF'}));
  const pdf=await screen.findByRole('img',{name:'PDF page 1, 2 highlighted words'});
  expect(JSON.parse(pdf.getAttribute('data-boxes')!)).toEqual([[.43,.12,.44,.14],[.45,.12,.46,.14]]);
  expect(screen.getByText(/Unreliable symbol boxes are omitted/)).toBeVisible();
});

it('switches from a table cell back to the caption without retaining cell highlights',async()=>{
  open({captionTable:true});const ui=userEvent.setup();
  await ui.click(await screen.findByRole('button',{name:'Show row 1, column 2 in PDF'}));
  expect(await screen.findByRole('img',{name:'PDF page 1, 1 highlighted words'})).toBeVisible();
  await ui.click(screen.getByRole('button',{name:'Show passage 1 in PDF'}));
  const pdf=await screen.findByRole('img',{name:'PDF page 1, 2 highlighted words'});
  expect(JSON.parse(pdf.getAttribute('data-boxes')!)).toEqual(layout.words.map(w=>w.box));
});

it('highlights only the requested grouped-table value and renders column headers',async()=>{
  open({subcolumns:true});const ui=userEvent.setup();
  expect(await screen.findByRole('columnheader',{name:/Employment Share/})).toBeVisible();
  await ui.click(screen.getByRole('button',{name:'Show row 2, column 4 in PDF'}));
  const pdf=await screen.findByRole('img',{name:'PDF page 1, 1 highlighted words'});
  expect(JSON.parse(pdf.getAttribute('data-boxes')!)).toEqual([[.6,.2,.65,.22]]);
});
