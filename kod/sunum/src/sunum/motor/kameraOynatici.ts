/**
 * Kamera koreografisi oynatıcısı.
 *
 * Her adım girişinde: (1) `bas` kamerası anında oturtulur (kesme), (2) `adimlar` uçuşları
 * sırayla oynatılır, (3) `girisMs` dolduğunda `mesgul` düşer ve varsa yörünge başlar.
 *
 * `mesgul` bayrağını QA kullanır: ekran görüntüsü ancak sahne oturduktan sonra alınır.
 * Yörünge `mesgul`ü AÇIK TUTMAZ — yoksa QA her karede 20 sn boşuna beklerdi.
 */
import { useEffect, useRef } from 'react';
import type { RefObject } from 'react';

import type { HaritaApi } from '../../map/HaritaSahnesi';
import type { KameraDegeri, SahneDurumu, SahneKamerasi } from './tipler';

export interface KameraOynaticiSecenekleri {
  haritaRef: RefObject<HaritaApi | null>;
  kamera: SahneKamerasi | null;
  /** adım kimliği — değişince koreografi baştan oynar */
  anahtar: string;
  durum: SahneDurumu;
  /** giriş animasyonunun bitiş süresi (ms) */
  girisMs?: number;
  onMesgul: (mesgul: boolean) => void;
}

export function useKameraOynatici({
  haritaRef,
  kamera,
  anahtar,
  durum,
  girisMs = 0,
  onMesgul,
}: KameraOynaticiSecenekleri): void {
  const durumRef = useRef(durum);
  durumRef.current = durum;
  const mesgulRef = useRef(onMesgul);
  mesgulRef.current = onMesgul;
  const kameraRef = useRef(kamera);
  kameraRef.current = kamera;
  const girisRef = useRef(girisMs);
  girisRef.current = girisMs;

  useEffect(() => {
    const api = haritaRef.current;
    if (!api) return;
    const k = kameraRef.current;
    let iptal = false;
    const coz = (d: KameraDegeri) => (typeof d === 'function' ? d({ api, durum: durumRef.current }) : d);

    mesgulRef.current(true);
    api.durdur();
    if (k?.bas) api.kameraAyarla(coz(k.bas));

    const baslangic = performance.now();
    void (async () => {
      for (const ad of k?.adimlar ?? []) {
        const tamamlandi = await api.flyTo(coz(ad.durum), ad.sureMs ?? 2000, { tur: ad.tur, egri: ad.egri });
        if (iptal) return;
        // kullanıcı araya girdiyse zinciri bırak (kendi uçuşumuz iptal edilirse zaten `iptal` true olur)
        if (!tamamlandi) break;
      }
      const kalan = girisRef.current - (performance.now() - baslangic);
      if (kalan > 0) await new Promise((r) => setTimeout(r, kalan));
      if (iptal) return;
      mesgulRef.current(false);
      if (k?.orbit) api.orbit(k.orbit);
    })();

    return () => {
      iptal = true;
    };
    // haritaRef kararlıdır; koreografi yalnız adım değişince yeniden oynar
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [anahtar]);
}
