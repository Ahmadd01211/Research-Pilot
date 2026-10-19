import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { getDocument } from 'pdfjs-dist';
import PdfCanvas from '../src/features/documents/pdf-canvas';
vi.mock('pdfjs-dist',()=>({GlobalWorkerOptions:{},getDocument:vi.fn()}));
const boxes: readonly [number,number,number,number][]=[];
beforeEach(()=>vi.clearAllMocks());
afterEach(()=>vi.unstubAllGlobals());
function digest() { vi.stubGlobal('crypto',{subtle:{digest:vi.fn().mockResolvedValue(new Uint8Array(32).fill(1).buffer)}}); }
it('never invokes the PDF parser when original bytes fail the checksum',async()=>{
  digest();vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(new Uint8Array([1,2,3]))));
  render(<PdfCanvas url="/api/v1/private-original" sourceHash={'00'.repeat(32)} page={1} boxes={boxes}/>);
  expect(await screen.findByRole('alert')).toHaveTextContent('No unverified PDF is displayed');
  expect(getDocument).not.toHaveBeenCalled();
});
it('does not parse a download that fails authorization',async()=>{
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(null,{status:401})));
  render(<PdfCanvas url="/api/v1/private-original" sourceHash={'01'.repeat(32)} page={1} boxes={boxes}/>);
  expect(await screen.findByRole('alert')).toBeVisible();
  expect(getDocument).not.toHaveBeenCalled();
});
it('passes only verified bytes and restrictive options to the PDF engine and destroys it on unmount',async()=>{
  digest();vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(new Uint8Array([1,2,3]))));
  const destroy=vi.fn().mockResolvedValue(undefined);
  vi.mocked(getDocument).mockReturnValue({promise:new Promise(()=>{}),destroy} as unknown as ReturnType<typeof getDocument>);
  const view=render(<PdfCanvas url="/api/v1/private-original" sourceHash={'01'.repeat(32)} page={1} boxes={boxes}/>);
  await waitFor(()=>expect(getDocument).toHaveBeenCalledWith(expect.objectContaining({isEvalSupported:false,enableXfa:false,useWasm:false,data:expect.any(Uint8Array)})));
  view.unmount();expect(destroy).toHaveBeenCalled();
});
