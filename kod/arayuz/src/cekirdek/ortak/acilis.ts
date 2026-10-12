/**
 * Açılış perdesi (index.html #acilis: işaret + ince ilerleme çizgisi) — ilk GERÇEK veri gelene dek durur.
 *
 * Perdeyi tutanlar: tembel yüklenen ekranın bekleme parçası (Suspense fallback) ve ilk verisini bekleyen
 * sağlayıcılar (ör. TASKS deposu). `acilisTut()` bir bırakma işlevi döner. Kimse tutmuyorsa perde kısa bir
 * gecikmeyle (zincirleme tembel yükleme arasında yanıp sönmesin diye) yumuşakça kalkar. En geç
 * EN_COK_MS sonra her durumda kalkar: veri gelmese bile ekran kendi bekleme/hata hâlini gösterir.
 */

import { useEffect } from 'react';

const EN_COK_MS = 8000;
const BEKLE_MS = 80;
const SOLMA_MS = 220;

let tutan = 0;
let serbest = false;
let bitti = false;
let zamanlayici = 0;
let sinir = 0;

function kaldir(): void {
  if (bitti) return;
  bitti = true;
  window.clearTimeout(zamanlayici);
  window.clearTimeout(sinir);
  const p = document.getElementById('acilis');
  kabugaBildir();
  if (!p) return;
  p.classList.add('bitti');
  window.setTimeout(() => p.remove(), SOLMA_MS);
}

/** Masaüstü kabuğu (Turkcell.exe, pywebview) açılış zaman çizelgesini kapatsın; tarayıcı/telefonda yok. */
function kabugaBildir(): void {
  try {
    const api = (window as unknown as { pywebview?: { api?: { acilis_bitti?: () => unknown } } }).pywebview?.api;
    void api?.acilis_bitti?.();
  } catch {
    /* kabuk yok */
  }
}

function denetle(): void {
  if (bitti || !serbest) return;
  window.clearTimeout(zamanlayici);
  zamanlayici = window.setTimeout(() => {
    if (tutan <= 0) kaldir();
  }, BEKLE_MS);
}

/** Oturum belli oldu: artık tutan yoksa perde kalkabilir (giriş ekranı için hemen). */
export function acilisSerbest(hemen = false): void {
  if (bitti) return;
  if (hemen) return kaldir();
  if (!serbest) {
    serbest = true;
    sinir = window.setTimeout(kaldir, EN_COK_MS);
  }
  denetle();
}

/** Perdeyi ilk veriye dek tut; dönen işlev bırakır (bir kez). */
export function acilisTut(): () => void {
  if (bitti) return () => undefined;
  tutan += 1;
  let birakildi = false;
  return () => {
    if (birakildi) return;
    birakildi = true;
    tutan -= 1;
    denetle();
  };
}

/** Bileşen bağlıyken (ve `tut` doğruyken) perdeyi tutar. */
export function useAcilisTut(tut = true): void {
  useEffect(() => (tut ? acilisTut() : undefined), [tut]);
}
