/**
 * Platform köprüsü — aynı kod hem Electron kabuğunda hem de tek dosya HTML'de çalışır.
 *
 * Electron tarafı `electron/preload.cjs` içinde `window.dsaleMasaustu` olarak açılır.
 * Köprü yoksa tarayıcı yedekleri kullanılır: gizli `<input type="file">` ve Fullscreen API.
 */

export interface PlanDosyasi {
  ad: string;
  /** dosya içeriği (JSON metni) */
  icerik: string;
}

export interface MasaustuKoprusu {
  surum: string;
  /** Dosya iletişim kutusunu açar; iptal edilirse null. */
  planAc(): Promise<PlanDosyasi | null>;
  /** Menüden "Plan Aç…" seçildiğinde tetiklenir. */
  onPlanYuklendi(cb: (d: PlanDosyasi) => void): () => void;
  /** Menüden Görünüm › Sunum/Keşif seçildiğinde. */
  onModDegistir(cb: (mod: string) => void): () => void;
  tamEkranDegistir(): void;
  tamEkranMi(): Promise<boolean>;
}

declare global {
  interface Window {
    dsaleMasaustu?: MasaustuKoprusu;
  }
}

/** Electron kabuğunda mıyız? */
export function masaustuMu(): boolean {
  return typeof window !== 'undefined' && !!window.dsaleMasaustu;
}

/** Masaüstü köprüsü (yoksa undefined). */
export function kopru(): MasaustuKoprusu | undefined {
  return typeof window === 'undefined' ? undefined : window.dsaleMasaustu;
}

/* ------------------------------------------------------------------ plan dosyası */

let _girdi: HTMLInputElement | null = null;

function dosyaGirdisi(): HTMLInputElement {
  if (_girdi) return _girdi;
  const el = document.createElement('input');
  el.type = 'file';
  el.accept = '.json,application/json';
  el.style.display = 'none';
  el.id = 'dsale-plan-dosya';
  document.body.appendChild(el);
  _girdi = el;
  return el;
}

/**
 * Plan dosyası seçtirir. Electron'da yerel iletişim kutusu, tarayıcıda gizli input.
 * QA `setInputFiles('#dsale-plan-dosya', …)` ile aynı yolu kullanabilir.
 */
export function planDosyasiAc(): Promise<PlanDosyasi | null> {
  const k = kopru();
  if (k) return k.planAc();
  return new Promise((coz) => {
    const el = dosyaGirdisi();
    el.onchange = async () => {
      const f = el.files?.[0];
      el.value = '';
      if (!f) return coz(null);
      coz({ ad: f.name, icerik: await f.text() });
    };
    el.click();
  });
}

/** Menü/IPC ile gelen plan dosyalarını dinler (yalnız Electron). */
export function onPlanYuklendi(cb: (d: PlanDosyasi) => void): () => void {
  return kopru()?.onPlanYuklendi(cb) ?? (() => {});
}

/** Menüden mod değişimi (yalnız Electron). */
export function onModDegistir(cb: (mod: string) => void): () => void {
  return kopru()?.onModDegistir(cb) ?? (() => {});
}

/* ------------------------------------------------------------------ tam ekran */

export function tamEkranDegistir(): void {
  const k = kopru();
  if (k) return k.tamEkranDegistir();
  const d = document;
  if (d.fullscreenElement) void d.exitFullscreen?.();
  else void d.documentElement.requestFullscreen?.().catch(() => {});
}

/* ------------------------------------------------------------------ sürükle-bırak */

/**
 * Pencereye .json sürüklenmesini dinler. Dönüş: aboneliği iptal eden fonksiyon.
 */
export function surukleBirak(cb: (d: PlanDosyasi) => void): () => void {
  if (typeof window === 'undefined') return () => {};
  const engelle = (e: DragEvent) => {
    e.preventDefault();
  };
  const birak = async (e: DragEvent) => {
    e.preventDefault();
    const f = e.dataTransfer?.files?.[0];
    if (!f || !/\.json$/i.test(f.name)) return;
    cb({ ad: f.name, icerik: await f.text() });
  };
  window.addEventListener('dragover', engelle);
  window.addEventListener('drop', birak);
  return () => {
    window.removeEventListener('dragover', engelle);
    window.removeEventListener('drop', birak);
  };
}
