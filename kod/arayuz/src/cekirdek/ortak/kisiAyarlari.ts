/**
 * Kişisel ayarlar (Kabuk ▸ Ayarlar paneli) — SUNUCUDA kişi başına (`GET/PUT /api/isler/tercih` içinde `ayarlar`),
 * cihazda yalnız anında açılış için kopya. MAP: durum sayaç çubuğu, lejant, otomatik tazeleme aralığı;
 * TASKS/MAP süzgeç değer listesi: diğer süzgeçlerle gizlenen değerler soluk mu gösterilsin.
 * Kim: cekirdek/konsol/AyarlarPaneli.tsx (düzenler), birimler/operasyon/isler/IsHaritasiEkrani.tsx ve
 * SuzgecMenusu.tsx DegerSecici (okur).
 * İzin: is.liste yoksa sunucuya gidilmez, varsayılanlar kullanılır.
 */

import { useEffect, useSyncExternalStore } from 'react';
import { tercihGetir, tercihYaz, type KisiAyarlari } from '../is/api';
import { yerelJsonOku, yerelJsonYaz } from './yerel';
import { useOturum } from '../yerel/oturum';

export type { KisiAyarlari } from '../is/api';

export const AYAR_VARSAYILAN: KisiAyarlari = {
  map_durum_cubugu: true,
  map_lejant: true,
  map_tazeleme_sn: 15,
  suzgec_soluk_goster: false,
};
export const TAZELEME_SECENEK: ReadonlyArray<{ sn: number; etiket: string }> = [
  { sn: 0, etiket: 'Kapalı' },
  { sn: 15, etiket: '15 sn' },
  { sn: 30, etiket: '30 sn' },
  { sn: 60, etiket: '1 dk' },
  { sn: 120, etiket: '2 dk' },
  { sn: 300, etiket: '5 dk' },
];

export function ayarOku(v: unknown): KisiAyarlari {
  const a = (v && typeof v === 'object' ? v : {}) as Partial<Record<keyof KisiAyarlari, unknown>>;
  const sn = a.map_tazeleme_sn;
  return {
    map_durum_cubugu: typeof a.map_durum_cubugu === 'boolean' ? a.map_durum_cubugu : AYAR_VARSAYILAN.map_durum_cubugu,
    map_lejant: typeof a.map_lejant === 'boolean' ? a.map_lejant : AYAR_VARSAYILAN.map_lejant,
    map_tazeleme_sn:
      typeof sn === 'number' && TAZELEME_SECENEK.some((x) => x.sn === sn) ? sn : AYAR_VARSAYILAN.map_tazeleme_sn,
    suzgec_soluk_goster:
      typeof a.suzgec_soluk_goster === 'boolean' ? a.suzgec_soluk_goster : AYAR_VARSAYILAN.suzgec_soluk_goster,
  };
}

let uid: number | null = null;
let ayar: KisiAyarlari = AYAR_VARSAYILAN;
const dinleyen = new Set<() => void>();
const yay = () => dinleyen.forEach((f) => f());
const kopya = (u: number) => `kisi.ayarlar.${u}`;
let zaman = 0;

function baslat(u: number | null, sunucu: boolean) {
  if (u === uid) return;
  uid = u;
  ayar = u == null ? AYAR_VARSAYILAN : ayarOku(yerelJsonOku<unknown>(kopya(u), null));
  yay();
  if (u == null || !sunucu) return;
  tercihGetir()
    .then((t) => {
      if (uid !== u || !t.ayarlar || zaman) return; // bekleyen yazma varsa sunucu kopyası ezmesin
      ayar = ayarOku(t.ayarlar);
      yerelJsonYaz(kopya(u), ayar);
      yay();
    })
    .catch(() => undefined);
}

/** Bir ayarı değiştir (0,5 sn sakinleşince sunucuya). */
export function ayarYaz(y: Partial<KisiAyarlari>) {
  ayar = { ...ayar, ...y };
  if (uid != null) yerelJsonYaz(kopya(uid), ayar);
  yay();
  if (zaman) window.clearTimeout(zaman);
  zaman = window.setTimeout(() => {
    zaman = 0;
    void tercihYaz({ ayarlar: ayar }).catch(() => undefined);
  }, 500);
}

export function useKisiAyarlari(): KisiAyarlari {
  const { kullanici, izinli } = useOturum();
  const u = kullanici?.id ?? null;
  const sunucu = izinli('is.liste');
  useEffect(() => baslat(u, sunucu), [u, sunucu]);
  return useSyncExternalStore(
    (f) => {
      dinleyen.add(f);
      return () => dinleyen.delete(f);
    },
    () => ayar,
  );
}
