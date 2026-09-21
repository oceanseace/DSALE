/**
 * Giriş noktası: fontları ve veriyi hazırlar, sözleşmeyi başlatır, uygulamayı bağlar,
 * sonra açılış perdesini (#acilis) söndürür.
 *
 * Sıra önemlidir: deck.gl TextLayer font atlasını fontlar yüklenmeden üretirse
 * etiketler yedek fontla çizilir ve bir daha düzelmez.
 */
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import './ui/global.css';
import App from './App';
import { UygulamaSaglayici } from './core/uygulama';
import { kontratBaslat } from './core/kontrat';
import { urlOku } from './core/url';
import { veri } from './data/load';
import { fontlariYukle } from './map/fontlar';

async function baslat() {
  const url = urlOku();
  await fontlariYukle();
  const v = veri();

  kontratBaslat({
    mod: url.mod,
    sahne: url.sahne ?? 1,
    adim: url.adim ?? 1,
    n: url.n ?? v.planPaketi.varsayilan,
    veriSurumu: v.meta.surum,
  });

  const kok = document.getElementById('root');
  if (!kok) throw new Error('#root bulunamadı');
  createRoot(kok).render(
    <StrictMode>
      <UygulamaSaglayici ilkMod={url.mod} ilkN={url.n}>
        <App />
      </UygulamaSaglayici>
    </StrictMode>,
  );

  // açılış perdesi: ilk kare çizilene kadar dursun
  const perdeyiKapat = () => {
    const el = document.getElementById('acilis');
    if (!el) return;
    el.style.opacity = '0';
    setTimeout(() => el.remove(), 700);
  };
  const bekle = setInterval(() => {
    if (window.__DSALE__?.hazir) {
      clearInterval(bekle);
      perdeyiKapat();
    }
  }, 120);
  setTimeout(() => {
    clearInterval(bekle);
    perdeyiKapat();
  }, 12000);
}

void baslat().catch((e) => {
  console.error('[dsale] açılış hatası', e);
  const el = document.getElementById('acilis');
  if (el) el.textContent = 'Uygulama açılamadı: ' + (e instanceof Error ? e.message : String(e));
});
