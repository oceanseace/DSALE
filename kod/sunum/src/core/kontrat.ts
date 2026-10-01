/**
 * `window.__DSALE__` — otomatik görsel testin (scripts/qa.mjs) uygulamayla tek sözleşmesi.
 *
 *   hazir        ilk gerçek kare çizildi + fontlar yüklendi → ekran görüntüsü alınabilir
 *   mesgul       kamera uçuyor / geçiş sürüyor → QA bunun bitmesini bekler
 *   mod          'sunum' | 'kesif'
 *   sahne        1 tabanlı sahne no
 *   sahneSayisi  toplam sahne
 *   adim         1 tabanlı sahne içi adım (varsa)
 *   n            etkin plan (bölge sayısı)
 *   git(n)       1 tabanlı sahneye atla
 *
 * SADECE bu dosya `window.__DSALE__` yazar. Sunum/Keşif `kontratGuncelle` çağırır.
 */
import type { Mod } from './url';

export interface DsaleKontrati {
  hazir: boolean;
  mesgul: boolean;
  mod: Mod;
  sahne: number;
  sahneSayisi: number;
  adim: number;
  adimSayisi: number;
  n: number;
  git: (sahne: number) => void;
  /** Keşif'in ek test kancası (additive; bkz. ARCHITECTURE.md) */
  kesif?: Record<string, unknown>;
  /** veri paketi sürümü — hangi verinin çizildiğini görmek için */
  veriSurumu?: number;
}

const BASLANGIC: DsaleKontrati = {
  hazir: false,
  mesgul: false,
  mod: 'sunum',
  sahne: 1,
  sahneSayisi: 1,
  adim: 1,
  adimSayisi: 1,
  n: 8,
  git: () => {},
};

declare global {
  interface Window {
    __DSALE__?: DsaleKontrati;
  }
}

function kap(): DsaleKontrati {
  if (typeof window === 'undefined') return { ...BASLANGIC };
  if (!window.__DSALE__) window.__DSALE__ = { ...BASLANGIC };
  return window.__DSALE__;
}

/** Sözleşmeyi başlatır (main.tsx bir kez çağırır). */
export function kontratBaslat(ilk: Partial<DsaleKontrati> = {}): DsaleKontrati {
  const k = kap();
  Object.assign(k, ilk);
  return k;
}

/** Alanları birleştirir; verilmeyen alanlar korunur. */
export function kontratGuncelle(p: Partial<DsaleKontrati>): void {
  Object.assign(kap(), p);
}

/** Anlık sözleşme (okuma). */
export function kontratOku(): DsaleKontrati {
  return kap();
}

/** hazir bayrağını bir kez kaldırır (ilk kare + fontlar). */
export function hazirBildir(): void {
  kontratGuncelle({ hazir: true });
  if (typeof document !== 'undefined') document.documentElement.setAttribute('data-dsale-hazir', '1');
}
