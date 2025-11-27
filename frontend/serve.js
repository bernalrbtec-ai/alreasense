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

// Serve static files from the dist directory
app.use(express.static(distPath));

// Handle client-side routing
app.get('*', (req, res) => {
  res.sendFile(indexPath);
});

app.listen(port, '0.0.0.0', () => {
  console.log(`🚀 Server running on http://0.0.0.0:${port}`);
  console.log(`📦 Environment: ${process.env.NODE_ENV || 'development'}`);
});
