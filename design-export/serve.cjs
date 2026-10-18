// Local-only preview. Restrict requests to the four public design assets.
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const assets = {
  '/': ['index.html', 'text/html; charset=utf-8'],
  '/index.html': ['index.html', 'text/html; charset=utf-8'],
  '/styles.css': ['styles.css', 'text/css; charset=utf-8'],
  '/app.js': ['app.js', 'text/javascript; charset=utf-8'],
  '/assets/Manrope.ttf': ['assets/Manrope.ttf', 'font/ttf'],
  '/assets/DMSans.ttf': ['assets/DMSans.ttf', 'font/ttf'],
};
const server = http.createServer((req, res) => {
  const asset = assets[new URL(req.url, 'http://localhost').pathname];
  if (!asset || !['GET', 'HEAD'].includes(req.method)) {
    res.writeHead(404); res.end('Not found'); return;
  }
  res.writeHead(200, {
    'Content-Type': asset[1], 'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff', 'X-Frame-Options': 'DENY',
    'Referrer-Policy': 'no-referrer',
  });
  if (req.method === 'HEAD') res.end();
  else fs.createReadStream(path.join(__dirname, asset[0])).pipe(res);
});
server.listen(3200, '127.0.0.1', () => console.log('ResearchPilot design: http://localhost:3200'));
