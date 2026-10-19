import { cp, mkdir } from 'node:fs/promises';
import { fileURLToPath, URL } from 'node:url';
const base = new URL('../', import.meta.url);
for (const directory of ['cmaps', 'standard_fonts']) {
  const target = new URL(`public/pdf-assets/${directory}/`, base);
  await mkdir(target, { recursive: true });
  await cp(fileURLToPath(new URL(`node_modules/pdfjs-dist/${directory}/`, base)), fileURLToPath(target), { recursive: true });
}


// Only inert image decoders; do not bundle the optional PDF scripting evaluator.
const decoderTarget = new URL('public/pdf-assets/decoders/',base);
await mkdir(decoderTarget,{recursive:true});
for (const file of ['openjpeg_nowasm_fallback.js','jbig2_nowasm_fallback.js','LICENSE_JBIG2','LICENSE_OPENJPEG','LICENSE_PDFJS_JBIG2','LICENSE_PDFJS_OPENJPEG']) {
  await cp(fileURLToPath(new URL(`node_modules/pdfjs-dist/wasm/${file}`,base)),fileURLToPath(new URL(file,decoderTarget)));
}
