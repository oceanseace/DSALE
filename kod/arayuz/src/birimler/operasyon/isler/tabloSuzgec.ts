/**
 * TASKS tablosunun otomatik süzgeci (Excel'deki ▾) ve sıralaması — durum + hesap, çizim yok.
 * Giriş: `useTabloSuzgec(liste, sutunlar)` → { suzulen, degerSayilari, sutunYaz, … }. Süzgeç durumu TASKS ile
 * MAP arasında ORTAK ve kişi başına sunucuda (tercihDeposu.ts).
 * Kim kullanır: Isler.tsx ve IsHaritasiEkrani.tsx (kurar), SuzgecMenusu.tsx (değer listesi), Tablo.tsx (▾, sıra oku),
 * map/MapSuzgec.tsx (MAP'in Filtreler çekmecesi).
 * Hız: her sütunun değerleri bir kez hesaplanıp önbelleğe alınır (3.000 satırda sayım < 100 ms).
 */

import { useCallback, useMemo } from 'react';
import type { IsaretRengi, IsSatir } from '../../../cekirdek/is/tipler';
import { katla } from '../../../cekirdek/ortak/ara';
import { COKLU_AYRAC, hucreRengi, RENK_ADI, type Sutun } from './sutunlar';
import { etkinDuzen, etkinYaz, suzgecYaz, useTercih, type Siralama, type SutunSuzgeci } from './tercihDeposu';

export type { Siralama, SutunSuzgeci } from './tercihDeposu';

export const BOS_ETIKET = '(Boşlar)';
const DIZICI = new Intl.Collator('tr', { numeric: true, sensitivity: 'base' });

/**
 * Değer listesi süzgeci — MAP'teki "İş türü" ile AYNI mantık (kullanıcının tarifi, 08.10):
 *   · işaretli kutular = kullanıcının SEÇTİĞİ değerler; kip yalnız ne yapılacağını söyler:
 *     "dahil" (Yalnız seçilenleri göster) → yalnız seçilenler · "haric" (Seçilenleri gizle) → seçilenler gizli;
 *   · kip değişince işaretler DEĞİŞMEZ; hiçbir şey seçili değilse süzgeç yoktur (hiçbir şey gizlenmez);
 *   · değer araması listeyi daraltır (Türkçe harf duyarsız, "içerir"); "Görünenleri seç" görünenleri seçime ekler.
 */
export function degerUyar(f: Pick<SutunSuzgeci, 'degerler' | 'kip'>, v: string): boolean {
  if (!f.degerler?.length) return true;
  return f.degerler.includes(v) !== (f.kip === 'haric');
}

/** Çok değerli sütunun (`coklu`) hücre değeri → tek tek değerler ('' → ['']: "(Boşlar)"). */
export function cokluAc(v: string): string[] {
  return v ? v.split(COKLU_AYRAC) : [''];
}

/** Çok değerli değer süzgeci: dahil → seçilenlerden BİRİ varsa geçer; hariç → seçilenlerden hiçbiri yoksa geçer. */
export function cokluUyar(f: Pick<SutunSuzgeci, 'degerler' | 'kip'>, v: string): boolean {
  if (!f.degerler?.length) return true;
  const k = new Set(f.degerler);
  return cokluAc(v).some((x) => k.has(x)) !== (f.kip === 'haric');
}

/** Süzgeç penceresinin başlangıcı: kayıtlı süzgeçteki seçim ve kip (süzgeç yoksa hiçbiri seçili değil). */
export function govdeBaslangic(f: SutunSuzgeci | undefined): { kip: 'dahil' | 'haric'; secim: Set<string> } {
  return { kip: f?.kip === 'haric' ? 'haric' : 'dahil', secim: new Set(f?.degerler ?? []) };
}

/** Değer listesinde ara: değeri (boşsa "(Boşlar)") aranan metni İÇEREN değerler, Türkçe harf duyarsız. */
export function degerAra<T extends [string, ...number[]]>(degerler: T[], ara: string): T[] {
  const q = katla(ara.trim());
  return q ? degerler.filter(([v]) => katla(v || BOS_ETIKET).includes(q)) : degerler;
}

/** Değer listesi satırı: [değer, toplam (bütün açık işlerde), görünür (diğer süzgeçlerden geçenlerde)]. */
export type DegerSatiri = [string, number, number];

/**
 * Süzgeç penceresinin değer listesi — MAP "İş türü" ile AYNI: liste DİĞER süzgeçlerden BAĞIMSIZ, bütün açık işlerin
 * değerleri (`tum`) sayılarıyla gelir; diğer süzgeçler yüzünden şu an görünmeyenler `gorunur = 0` olur (ekranda
 * gizlenir ya da Ayarlar'a göre soluk çizilir — bkz. degerGoster). Seçili olup hiçbir işte kalmayan değer de 0/0 ile listelenir (seçim kaybolmasın).
 * `sira`: 'ad' (A→Z, boş en sonda; `ornek` değerin sıralama anahtarı) ya da 'sayi' (çoktan aza, İş türü).
 */
export function degerListesi(
  tum: readonly string[],
  gorunur: readonly string[],
  secili: readonly string[] | null | undefined,
  sira: 'ad' | 'sayi' = 'ad',
  ornek?: ReadonlyMap<string, string>,
): DegerSatiri[] {
  const m = new Map<string, DegerSatiri>();
  for (const v of tum) {
    const x = m.get(v);
    if (x) x[1] += 1;
    else m.set(v, [v, 1, 0]);
  }
  for (const v of gorunur) {
    const x = m.get(v);
    if (x) x[2] += 1;
    else m.set(v, [v, 1, 1]);
  }
  for (const v of secili ?? []) if (!m.has(v)) m.set(v, [v, 0, 0]);
  const l = [...m.values()];
  if (sira === 'sayi') return l.sort((a, b) => b[1] - a[1] || DIZICI.compare(a[0], b[0]));
  return l.sort((a, b) =>
    a[0] === '' ? (b[0] === '' ? 0 : 1) : b[0] === '' ? -1 : DIZICI.compare(ornek?.get(a[0]) ?? a[0], ornek?.get(b[0]) ?? b[0]),
  );
}

/**
 * Süzgeç penceresinde GÖSTERİLECEK değerler (DegerSecici; 09.10) — `degerListesi`nin çıktısından:
 *   · `solukGoster` (Ayarlar ▸ "Diğer filtrelerle gizlenen değerleri soluk göster") açık → hepsi (gizlenenler soluk);
 *   · kapalı (varsayılan) → yalnız diğer süzgeçlerden geçen işlerde olan değerler (`gorunur > 0`);
 *   · arama yazılıysa her zaman BÜTÜN değerlerde arar (gizlenen eşleşmeler soluk çıkar — "kuru" listesi kurumasın);
 *   · seçili (işaretli) değer HER ZAMAN listede kalır (`secili`: şu anki ve pencere açılırkenki seçim).
 */
export function degerGoster(
  degerler: DegerSatiri[],
  ara: string,
  secili: { has(v: string): boolean },
  solukGoster: boolean,
): DegerSatiri[] {
  const l = degerAra(degerler, ara);
  if (solukGoster || ara.trim()) return l;
  return l.filter(([v, , g]) => g > 0 || secili.has(v));
}

/** "Görünenleri seç" / "(Tümünü seç)": görünen değerler seçime EKLENİR (önceki seçim kalır). */
export function gorunenleriSec(secim: Set<string>, gorunen: string[]): Set<string> {
  return new Set([...secim, ...gorunen]);
}

/** "(Tümünü seç)" işaretliyken basılırsa: görünenler seçimden çıkar. */
export function gorunenleriBirak(secim: Set<string>, gorunen: string[]): Set<string> {
  const g = new Set(gorunen);
  return new Set([...secim].filter((v) => !g.has(v)));
}

/** Tamam → saklanacak süzgeç. Seçim boşsa değer süzgeci yok (metin/renk süzgeci kalabilir). */
export function suzgecKur(
  kip: 'dahil' | 'haric',
  sec: string[],
  metin: string,
  renk?: IsaretRengi,
): SutunSuzgeci {
  const f: SutunSuzgeci = { degerler: sec.length ? [...sec] : null, metin };
  if (sec.length && kip === 'haric') f.kip = 'haric';
  if (renk) f.renk = renk;
  return f;
}

/** Süzgeç etkin mi (değer, metin ya da renk). */
export const suzgecEtkin = (f: SutunSuzgeci | undefined | null): boolean =>
  Boolean(f && (f.degerler?.length || f.metin || f.renk));

/** Sütun süzgeçleri TASKS ile MAP arasında ORTAK (tercihDeposu, kişi başına sunucuda); sıralama düzenin parçası. */
export function useTabloSuzgec(liste: IsSatir[], sutunlar: Sutun[], tum: IsSatir[] = liste) {
  const t = useTercih();
  const suzgec = t.suzgec.sutunlar;
  const siralama = etkinDuzen(t).sira ?? null;
  const setSiralama = useCallback((s: Siralama) => etkinYaz((d) => ({ ...d, sira: s })), []);

  const sutun = useMemo(() => new Map(sutunlar.map((c) => [c.id, c])), [sutunlar]);

  /* Sütun değerleri (süzgeç biçimi) satır sırasıyla; liste ya da sütunlar değişince sıfırlanır. */
  const onbellek = useMemo(() => new Map<string, string[]>(), [liste, sutunlar]); // eslint-disable-line react-hooks/exhaustive-deps
  const tumOnbellek = useMemo(() => new Map<string, string[]>(), [tum, sutunlar]); // eslint-disable-line react-hooks/exhaustive-deps
  const degerler = useCallback(
    (id: string): string[] => {
      let d = onbellek.get(id);
      if (!d) {
        const c = sutun.get(id);
        const f = c ? c.suzgec ?? c.deger : () => '';
        d = liste.map(f);
        onbellek.set(id, d);
      }
      return d;
    },
    [onbellek, sutun, liste],
  );

  /** Etkin süzgeçler: yalnız var olan sütunlar; her biri satır indeksine bakan bir sınama. */
  const etkin = useMemo(
    () =>
      Object.entries(suzgec)
        .filter(([id, f]) => sutun.has(id) && suzgecEtkin(f))
        .map(([id, f]) => {
          const kume = f.degerler?.length ? new Set(f.degerler) : null;
          const haric = f.kip === 'haric';
          const metin = katla(f.metin.trim());
          return {
            id,
            f,
            gecer: (i: number) => {
              const v = degerler(id)[i];
              if (kume && (sutun.get(id)!.coklu ? !cokluUyar(f, v) : kume.has(v) === haric)) return false;
              if (f.renk && hucreRengi(liste[i], id) !== f.renk) return false;
              return !metin || katla(sutun.get(id)!.deger(liste[i])).includes(metin);
            },
          };
        }),
    [suzgec, sutun, degerler, liste],
  );

  const suzulen = useMemo(() => {
    const idx: number[] = [];
    for (let i = 0; i < liste.length; i++) if (etkin.every((e) => e.gecer(i))) idx.push(i);
    const c = siralama ? sutun.get(siralama.id) : undefined;
    if (siralama && c) {
      const k = liste.map(c.sira ?? c.deger);
      // Excel gibi: boşlar iki yönde de en sonda.
      idx.sort((a, b) => {
        if (!k[a] || !k[b]) return !k[a] === !k[b] ? a - b : k[a] ? -1 : 1;
        return siralama.yon * DIZICI.compare(k[a], k[b]) || a - b;
      });
    } else {
      // Varsayılan: geliş sırası — yeni gelen iş en altta.
      idx.sort((a, b) => (liste[a].acilis ?? '').localeCompare(liste[b].acilis ?? '') || a - b);
    }
    return idx.map((i) => liste[i]);
  }, [liste, etkin, siralama, sutun]);

  /**
   * Sütunun değer listesi (TASKS ▾ ve MAP çekmecesi; İş türü ile aynı): bütün açık işlerin değerleri (diğer
   * süzgeçlerden bağımsız) + diğer etkin süzgeçlerden geçen satırlardaki sayısı (0 → soluk). Bkz. degerListesi.
   */
  const degerSayilari = useCallback(
    (id: string): DegerSatiri[] => {
      const digerleri = etkin.filter((e) => e.id !== id);
      const d = degerler(id);
      const c = sutun.get(id);
      let td = tum === liste ? d : tumOnbellek.get(id);
      if (!td) {
        const f = c ? c.suzgec ?? c.deger : () => '';
        td = tum.map(f);
        tumOnbellek.set(id, td);
      }
      const gorunur: string[] = [];
      for (let i = 0; i < liste.length; i++) if (digerleri.every((e) => e.gecer(i))) gorunur.push(d[i]);
      if (c?.coklu) return degerListesi(td.flatMap(cokluAc), gorunur.flatMap(cokluAc), suzgec[id]?.degerler, 'ad');
      let ornek: Map<string, string> | undefined;
      if (c?.sira) {
        ornek = new Map();
        for (let i = 0; i < tum.length; i++) if (!ornek.has(td[i])) ornek.set(td[i], c.sira(tum[i]));
      }
      return degerListesi(td, gorunur, suzgec[id]?.degerler, 'ad', ornek);
    },
    [etkin, degerler, sutun, liste, tum, tumOnbellek, suzgec],
  );

  const sutunYaz = useCallback((id: string, f: SutunSuzgeci | null) => {
    suzgecYaz((o) => {
      const y = { ...o.sutunlar };
      if (!suzgecEtkin(f)) delete y[id];
      else if (f) y[id] = f;
      return { ...o, sutunlar: y };
    });
  }, []);
  /** Sütundaki hücrelerin dolgu renkleri (Renge göre süz; DİĞER süzgeçlere göre). */
  const renkler = useCallback(
    (id: string): IsaretRengi[] => {
      const digerleri = etkin.filter((e) => e.id !== id);
      const k = new Set<IsaretRengi>();
      for (let i = 0; i < liste.length; i++) {
        const r = hucreRengi(liste[i], id);
        if (r && !k.has(r) && digerleri.every((e) => e.gecer(i))) k.add(r);
      }
      return [...k];
    },
    [etkin, liste],
  );
  const temizle = useCallback(() => suzgecYaz((o) => ({ ...o, sutunlar: {} })), []);

  return { suzgec, etkin, suzulen, siralama, setSiralama, degerSayilari, renkler, sutunYaz, temizle, sutun };
}
export type TabloSuzgec = ReturnType<typeof useTabloSuzgec>;

/** Çip metni (kısa): "Task adı: 15 değer" · "Task adı: gizli 15 değer" (1–2 değer adıyla). Ekranda en çok
 *  CIP_EN_COK karakter (…). */
export function cipMetni(baslik: string, f: SutunSuzgeci): string {
  const p: string[] = [];
  if (f.degerler?.length) {
    const d = f.degerler.map((v) => v || BOS_ETIKET);
    const m = d.length > 2 ? `${d.length.toLocaleString('tr-TR')} değer` : d.join(', ');
    p.push(f.kip === 'haric' ? `gizli ${m}` : m);
  }
  if (f.renk) p.push(`dolgu ${RENK_ADI[f.renk]}`);
  if (f.metin) p.push(`“${f.metin}” içerir`);
  return `${baslik}: ${p.join(' · ')}`;
}

/** Çipin üzerine gelince görünen tam metin (bütün seçili değerler, en çok 40). */
export function cipIpucu(baslik: string, f: SutunSuzgeci): string {
  const p: string[] = [];
  if (f.degerler?.length) {
    const d = f.degerler.map((v) => v || BOS_ETIKET);
    const m = d.slice(0, 40).join(', ') + (d.length > 40 ? ` … (+${d.length - 40})` : '');
    p.push(f.kip === 'haric' ? `gizlenen: ${m}` : `yalnız: ${m}`);
  }
  if (f.renk) p.push(`dolgu ${RENK_ADI[f.renk]}`);
  if (f.metin) p.push(`“${f.metin}” içerir`);
  return `${baslik}: ${p.join(' · ')}`;
}

export const CIP_EN_COK = 32;
export const cipKisalt = (s: string) => (s.length > CIP_EN_COK ? `${s.slice(0, CIP_EN_COK - 1).trimEnd()}…` : s);
