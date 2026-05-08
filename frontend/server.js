/* eslint-disable */
const express = require('express');
const path = require('path');
const fs = require('fs');

const PORT = parseInt(process.env.PORT || '3000', 10);
const HOST = process.env.HOST || '0.0.0.0';

// Load REACT_APP_BACKEND_URL from .env (simple parser, no extra dep needed)
let backendUrl = process.env.REACT_APP_BACKEND_URL || '';
try {
  const envPath = path.join(__dirname, '.env');
  if (fs.existsSync(envPath)) {
    const lines = fs.readFileSync(envPath, 'utf8').split(/\r?\n/);
    for (const line of lines) {
      const match = line.match(/^\s*REACT_APP_BACKEND_URL\s*=\s*(.+?)\s*$/);
      if (match) backendUrl = match[1].replace(/^['"]|['"]$/g, '');
    }
  }
} catch (_) {}

const app = express();

// Inject runtime config (window.__ENV__) before serving index.html
app.get(['/', '/index.html'], (req, res) => {
  const indexPath = path.join(__dirname, 'public', 'index.html');
  let html = fs.readFileSync(indexPath, 'utf8');
  const inject = `<script>window.__ENV__ = { REACT_APP_BACKEND_URL: ${JSON.stringify(backendUrl)} };</script>`;
  html = html.replace('</head>', `${inject}\n</head>`);
  res.setHeader('Content-Type', 'text/html; charset=utf-8');
  res.send(html);
});

// Static assets at /assets to match existing references
app.use('/assets', express.static(path.join(__dirname, 'public'), { fallthrough: true }));
app.use(express.static(path.join(__dirname, 'public')));

app.listen(PORT, HOST, () => {
  console.log(`Frontend dashboard listening on http://${HOST}:${PORT} (backend: ${backendUrl || '(unset)'})`);
});
