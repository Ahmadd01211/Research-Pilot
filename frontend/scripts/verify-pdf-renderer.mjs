// Read-only PDF input; static canvas verification, not browser screenshot automation.
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';
import { fileURLToPath, URL } from 'node:url';
import assert from 'node:assert/strict';
import process from 'node:process';
const require = createRequire(import.meta.url);
const canvasLibrary = require('@napi-rs/canvas');
for (const key of ['DOMMatrix','ImageData','Path2D']) globalThis[key] = canvasLibrary[key];
const fontDirectory = fileURLToPath(new URL('../node_modules/pdfjs-dist/standard_fonts/',import.meta.url)).replaceAll(String.fromCharCode(92), '/');
const { getDocument } = await import('pdfjs-dist/legacy/build/pdf.mjs');
const [source, metadata, output] = process.argv.slice(2);
if (!source || !metadata || !output) throw new Error('Provide PDF, parser JSON and output directory');
const data = new Uint8Array(await readFile(source));
const layouts = JSON.parse(await readFile(metadata,'utf8')).layouts;
assert(Array.isArray(layouts));
const options = { data, isEvalSupported:false, useWasm:false, enableXfa:false,
  standardFontDataUrl:fontDirectory };
const loadingTask = getDocument(options); const document = await loadingTask.promise;
assert.equal(document.numPages,layouts.length);
await mkdir(output,{recursive:true});
for (let n=1;n<=Math.min(3,document.numPages);n++) {
  const page = await document.getPage(n);
  const viewport = page.getViewport({scale:1.15});
  const layout = layouts[n-1];
  assert(Math.abs(viewport.width/viewport.height - layout.width/layout.height)<0.001);
  const canvas = canvasLibrary.createCanvas(Math.ceil(viewport.width),Math.ceil(viewport.height));
  const context = canvas.getContext('2d');
  await page.render({canvas,canvasContext:context,viewport}).promise;
  const passage=layout.passages[0];
  assert(passage?.word_indices.length>0);
  context.fillStyle='rgba(250,204,21,.35)';
  for (const i of passage.word_indices) {
    const [x0,y0,x1,y1]=layout.words[i].box;
    assert(x1>x0&&y1>y0&&x0>=0&&x1<=1&&y0>=0&&y1<=1);
    context.fillRect(x0*viewport.width,y0*viewport.height,(x1-x0)*viewport.width,(y1-y0)*viewport.height);
  }
  await writeFile(resolve(output,`verified-page-${n}.png`),canvas.toBuffer('image/png'));
}
await loadingTask.destroy();
process.stdout.write('PDF.js rendered original pages with matching crop ratios and measured word highlights.\n');



