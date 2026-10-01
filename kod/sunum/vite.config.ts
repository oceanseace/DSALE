import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { viteSingleFile } from 'vite-plugin-singlefile';

/**
 * İki derleme hedefi:
 *  - `vite build`              → dist/        (Electron kabuğu için; varlıklar ayrı dosyalar)
 *  - `vite build --mode html`  → dist-html/   (tek başına index.html; JS + CSS + veri + fontlar gömülü)
 * Çıktı klasörü CLI'dan değiştirilebilir:  npm run build:html -- --outDir ../ciktim
 * base './' → her şey file:// üzerinden çalışır.
 */
export default defineConfig(({ mode }) => {
  const tekDosya = mode === 'html';
  return {
    base: './',
    plugins: [react(), ...(tekDosya ? [viteSingleFile({ removeViteModuleLoader: true })] : [])],
    build: {
      outDir: tekDosya ? 'dist-html' : 'dist',
      emptyOutDir: true,
      target: 'es2022',
      chunkSizeWarningLimit: 40000,
      reportCompressedSize: false,
      assetsInlineLimit: tekDosya ? 100_000_000 : 4096,
      cssCodeSplit: !tekDosya,
    },
    server: { port: 5178, strictPort: false },
  };
});
