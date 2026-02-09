import express from 'express';
import path from 'path';
import { fileURLToPath } from 'url';
import { existsSync, readdirSync } from 'fs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const port = process.env.PORT || 80;

const distPath = path.join(__dirname, 'dist');
const indexPath = path.join(distPath, 'index.html');

// Verificar se dist existe
if (!existsSync(distPath)) {
  console.error(`❌ ERROR: dist directory not found at ${distPath}`);
  console.error('Current directory:', __dirname);
  console.error('Files in current directory:', readdirSync(__dirname));
  process.exit(1);
}

if (!existsSync(indexPath)) {
  console.error(`❌ ERROR: index.html not found at ${indexPath}`);
  process.exit(1);
}

console.log(`✅ Serving files from: ${distPath}`);
console.log(`✅ Index file: ${indexPath}`);

// Evitar "Failed to fetch dynamically imported module": index.html não deve ser cacheado,
// para que após cada deploy o cliente baixe o HTML novo com os hashes corretos dos JS.
// Assets em /assets/ são hashed e podem ser cacheados por muito tempo.
app.use(express.static(distPath, {
  setHeaders: (res, filePath) => {
    const isIndex = filePath === indexPath || filePath.endsWith(path.sep + 'index.html');
    if (isIndex) {
      res.set('Cache-Control', 'no-cache, no-store, must-revalidate');
    } else if (filePath.includes(path.sep + 'assets' + path.sep)) {
      res.set('Cache-Control', 'max-age=31536000, immutable');
    }
  },
}));

// Handle client-side routing (SPA fallback)
app.get('*', (req, res) => {
  res.set('Cache-Control', 'no-cache, no-store, must-revalidate');
  res.sendFile(indexPath);
});

app.listen(port, '0.0.0.0', () => {
  console.log(`🚀 Server running on http://0.0.0.0:${port}`);
  console.log(`📦 Environment: ${process.env.NODE_ENV || 'development'}`);
});
