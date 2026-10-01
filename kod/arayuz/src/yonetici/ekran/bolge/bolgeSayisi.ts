/**
 * Etkin bölge sayısı (sözleşme §7.7): bölge planı uygulanınca 8 olmaktan çıkar.
 *
 * Ekip, Kapsama ve Rapor ekranlarındaki "1-8. bölge" listeleri buradan beslenir;
 * yoksa 14 bölgeye geçildiğinde 9-14. bölgenin satışçısına bölge verilemezdi.
 * Değer bir kez okunur, bütün ekranlar paylaşır; plan uygulanınca / geri
 * alınınca `bolgeSayisiniTazele()` çağrılır.
 */

import { useEffect, useState } from 'react';
import { bolgeSayisiOku } from '../../api';

let deger = 8;
let soz: Promise<number> | null = null;
const dinleyiciler = new Set<(n: number) => void>();

function oku(): Promise<number> {
  if (!soz) {
    soz = bolgeSayisiOku()
      .then((n) => {
        deger = n;
        dinleyiciler.forEach((d) => d(n));
        return n;
      })
      .catch(() => {
        soz = null; // bir sonraki ekranda tekrar denensin
        return deger;
      });
  }
  return soz;
}

export function bolgeSayisiniTazele(yeni?: number) {
  if (yeni && yeni > 0) {
    deger = yeni;
    soz = Promise.resolve(yeni);
    dinleyiciler.forEach((d) => d(yeni));
    return;
  }
  soz = null;
  void oku();
}

export function useBolgeSayisi(): number {
  const [n, setN] = useState(deger);
  useEffect(() => {
    dinleyiciler.add(setN);
    void oku().then(setN);
    return () => {
      dinleyiciler.delete(setN);
    };
  }, []);
  return n;
}

/** 1..n */
export function bolgeNumaralari(n: number): number[] {
  return Array.from({ length: Math.max(0, n) }, (_, i) => i + 1);
}
