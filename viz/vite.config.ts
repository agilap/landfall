import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// base './' keeps asset paths relative so a static export (e.g. GitHub Pages
// under a subpath) resolves data/ and JS bundles correctly.
export default defineConfig({
  base: './',
  plugins: [react()],
});
