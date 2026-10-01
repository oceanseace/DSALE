import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';
import './stil/temel.css';

const kok = document.getElementById('kok');
if (!kok) throw new Error('#kok bulunamadı');

createRoot(kok).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

/* Servis çalışanı: uygulamanın çevrimdışı açılmasını sağlar. */
if ('serviceWorker' in navigator && import.meta.env.PROD) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(() => {
      /* HTTP üzerinden açıldıysa kayıt olmaz; uygulama yine çalışır */
    });
  });

  /*
   * Yeni sürüm kurulunca sayfa eski kodla açık kalmasın. Kabuk önbellekten
   * açıldığı için güncellemeden sonraki İLK yenileme eski sürümü gösteriyordu.
   * Sayfa yeni açıldıysa (kullanıcı henüz bir şey yazmadıysa) kendini bir kez
   * yeniler; uzun süredir açıksa formu bozmamak için yenilemeyi bir sonraki
   * açılışa bırakır.
   */
  const ilkKontrolcu = !!navigator.serviceWorker.controller;
  let yenilendi = false;
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (!ilkKontrolcu || yenilendi) return; // ilk kurulum: zaten güncel kod çalışıyor
    if (performance.now() < 20_000) {
      yenilendi = true;
      window.location.reload();
    }
  });
}

/* iOS'ta çift dokunuşla yakınlaşmayı kapat — düğmeye basarken sayfa zıplamasın. */
document.addEventListener(
  'dblclick',
  (olay) => {
    olay.preventDefault();
  },
  { passive: false },
);
