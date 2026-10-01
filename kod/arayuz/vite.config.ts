import { defineConfig, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';
import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

/**
 * Elle yazılmış servis çalışanı (service worker).
 * Derleme bittiğinde üretilen dosya adlarını `sw.js` şablonuna gömer; böylece
 * uygulama kabuğu ilk açılışta önbelleğe alınır ve internet olmadan da açılır.
 * Dış bağımlılık (workbox vb.) yok — tek dosya, okunabilir, öngörülebilir.
 */
function servisCalisani(): Plugin {
  let cikisDizini = 'dist';
  return {
    name: 'saha-servis-calisani',
    apply: 'build',
    configResolved(cfg) {
      cikisDizini = cfg.build.outDir;
    },
    generateBundle(_secenek, paket) {
      /*
       * Kurulumda indirilecek dosyalar. Harita motoru (deck.gl, ~216 kB gzip)
       * BİLEREK dışarıda: ilk açılışta uygulamanın kurulmasını geciktirmesin.
       * Satışçı "Harita" sekmesine ilk girdiğinde indirilir ve servis
       * çalışanının `/varlik/` kuralı onu oracıkta önbelleğe alır — yani
       * çevrimdışı harita yine çalışır, sadece bir kez açılmış olması gerekir.
       */
      const dosyalar = Object.keys(paket)
        .filter((ad) => /\.(js|css|woff2?|png|svg|webmanifest)$/.test(ad))
        .filter((ad) => !/^varlik\/harita-/.test(ad))
        .map((ad) => '/' + ad);
      // public/ dosyaları pakette görünmez: index.html'in ilk karede okuduğu tema
      // betiği (koyu/açık parlamasın) çevrimdışı ilk açılışta da gelmeli.
      const liste = ['/', '/index.html', '/manifest.webmanifest', '/tema-erken.js', ...dosyalar];
      const surum = Date.now().toString(36);
      const sablon = readFileSync(resolve(__dirname, 'src/sw.js'), 'utf8')
        .replace('__SAHA_SURUM__', surum)
        .replace('__SAHA_KABUK__', JSON.stringify(liste, null, 2));
      this.emitFile({ type: 'asset', fileName: 'sw.js', source: sablon });
    },
    closeBundle() {
      // Derleme sonrası küçük bir özet — QA betiği bunu okuyabiliyor.
      try {
        writeFileSync(
          resolve(__dirname, cikisDizini, 'derleme.json'),
          JSON.stringify({ zaman: new Date().toISOString() }, null, 2),
          'utf8',
        );
      } catch {
        /* özet yazılamazsa derleme yine de geçerli */
      }
    },
  };
}

export default defineConfig({
  base: '/',
  plugins: [react(), servisCalisani()],
  build: {
    target: 'es2020',
    outDir: 'dist',
    assetsDir: 'varlik',
    sourcemap: false,
    chunkSizeWarningLimit: 1600,
    rollupOptions: {
      output: {
        manualChunks(id) {
          /*
           * Vite'in `__vitePreload` yardımcısı sanal bir modüldür ve
           * node_modules altında görünmez. Hiçbir yere atanmazsa Rollup onu
           * rastgele bir parçaya (bizde deck.gl parçasına) koyuyor; giriş
           * parçası o tek fonksiyon için 732 kB'lık harita motorunu STATİK
           * bağımlılık hâline getiriyor ve satışçı PIN ekranını görmeden
           * 216 kB indiriyordu. Yardımcıyı zaten her zaman yüklenen
           * `saticilar` parçasına sabitliyoruz.
           */
          if (id.includes('vite/preload-helper') || id.includes('vite/modulepreload')) {
            return 'saticilar';
          }
          if (id.includes('node_modules')) {
            if (id.includes('deck.gl') || id.includes('luma.gl') || id.includes('loaders.gl')) return 'harita';
            return 'saticilar';
          }
          return undefined;
        },
      },
    },
  },
  server: {
    host: '127.0.0.1',
    port: 5180,
    // Geliştirme sunucusu: kod/saha/GELISTIRME_BASLAT.bat (127.0.0.1:8090). 8080 canlıdır, vekil oraya gitmez.
    proxy: {
      '/api': { target: 'http://127.0.0.1:8090', changeOrigin: false },
    },
  },
  preview: { host: '127.0.0.1', port: 4173 },
});
