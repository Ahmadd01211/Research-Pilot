import { useEffect, useRef, useState } from 'react';
import { getDocument, GlobalWorkerOptions, type PDFDocumentProxy } from 'pdfjs-dist';
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
GlobalWorkerOptions.workerSrc = workerUrl;
type Box = readonly [number, number, number, number];

export default function PdfCanvas({ url, sourceHash, page, boxes }: { url: string; sourceHash?: string; page: number; boxes: readonly Box[] }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [loaded, setLoaded] = useState<{ url: string; hash?: string; pdf?: PDFDocumentProxy; error?: string }>();
  const [zoom, setZoom] = useState(1);
  const [rendered, setRendered] = useState<{ pdf: PDFDocumentProxy; page: number; zoom: number; boxes: readonly Box[]; error?: string }>();
  useEffect(() => {
    if (!sourceHash) return;
    let active = true;
    const controller = new AbortController();
    let task: ReturnType<typeof getDocument> | undefined;
    void (async () => {
      try {
        const response = await fetch(url, { credentials: 'same-origin', cache: 'no-store', signal: controller.signal });
        if (!response.ok) throw new Error('Original unavailable');
        const bytes = await response.arrayBuffer();
        if (bytes.byteLength > 20 * 1024 * 1024) throw new Error('Original exceeds limits');
        const digest = await crypto.subtle.digest('SHA-256',bytes);
        const hash = Array.from(new Uint8Array(digest),b=>b.toString(16).padStart(2,'0')).join('');
        if (hash !== sourceHash) throw new Error('Original integrity mismatch');
        if (!active) return;
        const options = { data: new Uint8Array(bytes), isEvalSupported: false, enableXfa: false,
          useWasm: false, wasmUrl: '/pdf-assets/decoders/', maxImageSize: 16_000_000, canvasMaxAreaInBytes: 48_000_000, stopAtErrors: true, cMapUrl: '/pdf-assets/cmaps/', cMapPacked: true, standardFontDataUrl: '/pdf-assets/standard_fonts/' };
        task = getDocument(options);
        const pdf = await task.promise;
        if (active) setLoaded({ url, hash: sourceHash, pdf });
      } catch { if (active) setLoaded({ url, hash: sourceHash, error: 'The original could not be opened or its checksum did not match. No unverified PDF is displayed. Try reopening the reader or restoring the original.' }); }
    })();
    return () => { active = false; controller.abort(); void task?.destroy(); };
  }, [url, sourceHash]);
  const pdf = loaded?.url === url && loaded.hash === sourceHash ? loaded.pdf : undefined;
  useEffect(() => {
    if (!pdf || !canvas.current) return;
    let active = true;
    let task: ReturnType<Awaited<ReturnType<PDFDocumentProxy['getPage']>>['render']> | undefined;
    const target = canvas.current;
    target.width = 1; target.height = 1;
    void (async () => {
      try {
        const source = await pdf.getPage(page);
        if (!active) return;
        const natural = source.getViewport({ scale: 1 });
        if (!Number.isFinite(natural.width) || !Number.isFinite(natural.height) || natural.width <= 0 || natural.height <= 0) throw new Error('Invalid page');
        const scale = Math.min(1.5 * zoom, Math.sqrt(12_000_000 / (natural.width * natural.height)), 8000 / Math.max(natural.width, natural.height));
        const viewport = source.getViewport({ scale });
        target.width = Math.ceil(viewport.width); target.height = Math.ceil(viewport.height);
        const context = target.getContext('2d');
        if (!context) throw new Error('Canvas unavailable');
        task = source.render({ canvas: target, canvasContext: context, viewport });
        await task.promise;
        if (!active) return;
        context.fillStyle = 'rgba(250, 204, 21, 0.35)';
        context.strokeStyle = 'rgba(161, 98, 7, 0.65)';
        for (const [x0,y0,x1,y1] of boxes) {
          context.fillRect(x0 * viewport.width, y0 * viewport.height, (x1-x0) * viewport.width, (y1-y0) * viewport.height);
          context.strokeRect(x0 * viewport.width, y0 * viewport.height, (x1-x0) * viewport.width, (y1-y0) * viewport.height);
        }
        setRendered({ pdf, page, zoom, boxes });
      } catch { if (active) setRendered({ pdf, page, zoom, boxes, error: 'This page could not be rendered. The original download and extracted text remain available.' }); }
    })();
    return () => { active = false; task?.cancel(); };
  }, [pdf, page, zoom, boxes]);
  const current = rendered?.pdf === pdf && rendered?.page === page && rendered?.zoom === zoom && rendered?.boxes === boxes ? rendered : undefined;
  const error = loaded?.url === url && loaded.hash === sourceHash ? loaded.error ?? current?.error : undefined;
  return <section className="reader-original" aria-label="Original PDF viewer"><div className="between reader-panel-heading"><h2>Original PDF</h2><div className="row gap8"><button className="btn" disabled={zoom <= .75} onClick={() => setZoom(z => Math.max(.75,z-.25))} aria-label="Zoom out">−</button><span>{Math.round(zoom*100)}%</span><button className="btn" disabled={zoom >= 2} onClick={() => setZoom(z => Math.min(2,z+.25))} aria-label="Zoom in">+</button></div></div>{error ? <p role="alert" className="alert mt16">{error}</p> : !current && <p role="status" className="muted tiny mt16">Rendering original page…</p>}<div className={`pdf-scroll zoom-${Math.round(zoom*100)}`} aria-busy={!current && !error}><canvas ref={canvas} className={!current ? 'pdf-pending' : undefined} role="img" aria-label={`Original PDF page ${page}${boxes.length ? ', selected passage highlighted' : ''}`}>Use the extracted-text panel or download the original to read this page.</canvas></div></section>;
}


