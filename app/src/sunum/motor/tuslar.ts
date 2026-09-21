/**
 * Sunum kumandası: klavye, fare ve sunum kumandası (clicker) tuşları.
 *
 *   →  PageDown  Boşluk  Enter   ileri
 *   ←  PageUp    Backspace       geri
 *   Home / End                   ilk / son sahne
 *   F                            film (otomatik oynatma) aç-kapa
 *   1..9, 0                      sahneye atla (0 = 10)
 *   Sol tık ileri · sağ tık geri (kumandaların çoğu ok tuşu üretir)
 *
 * `data-etkilesim="1"` taşıyan bir öğenin içindeki tık ve tuşlar yok sayılır
 * (S9 kaydırıcısı gibi etkileşimli parçalar sahneyi ilerletmemeli).
 */
import { useEffect, useRef } from 'react';

export interface TusEylemleri {
  ileri: () => void;
  geri: () => void;
  git: (sahne: number) => void;
  basa: () => void;
  sona: () => void;
  filmDegistir: (acik?: boolean) => void;
  sahneSayisi: number;
}

function etkilesimliMi(hedef: EventTarget | null): boolean {
  const el = hedef as HTMLElement | null;
  if (!el || typeof el.closest !== 'function') return false;
  if (/^(INPUT|TEXTAREA|SELECT|BUTTON)$/.test(el.tagName)) return true;
  return !!el.closest('[data-etkilesim="1"]');
}

export function useTuslar(eylem: TusEylemleri): void {
  const ref = useRef(eylem);
  ref.current = eylem;

  useEffect(() => {
    const tus = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.altKey || e.metaKey) return;
      if (etkilesimliMi(e.target)) return;
      const k = e.key;
      if (k === 'ArrowRight' || k === 'PageDown' || k === ' ' || k === 'Spacebar' || k === 'Enter') {
        e.preventDefault();
        ref.current.ileri();
      } else if (k === 'ArrowLeft' || k === 'PageUp' || k === 'Backspace') {
        e.preventDefault();
        ref.current.geri();
      } else if (k === 'Home') {
        e.preventDefault();
        ref.current.basa();
      } else if (k === 'End') {
        e.preventDefault();
        ref.current.sona();
      } else if (!e.shiftKey && (k === 'f' || k === 'F')) {
        e.preventDefault();
        ref.current.filmDegistir();
      } else if (k === 'Escape') {
        ref.current.filmDegistir(false);
      } else if (/^[0-9]$/.test(k)) {
        const no = k === '0' ? 10 : Number(k);
        if (no <= ref.current.sahneSayisi) {
          e.preventDefault();
          ref.current.git(no);
        }
      }
    };

    const tik = (e: MouseEvent) => {
      if (e.button !== 0) return;
      if (etkilesimliMi(e.target)) return;
      ref.current.ileri();
    };
    const sagTik = (e: MouseEvent) => {
      e.preventDefault();
      if (etkilesimliMi(e.target)) return;
      ref.current.geri();
    };

    window.addEventListener('keydown', tus);
    window.addEventListener('click', tik);
    window.addEventListener('contextmenu', sagTik);
    return () => {
      window.removeEventListener('keydown', tus);
      window.removeEventListener('click', tik);
      window.removeEventListener('contextmenu', sagTik);
    };
  }, []);
}
