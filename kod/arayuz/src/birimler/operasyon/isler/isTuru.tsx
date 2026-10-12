/**
 * İş türü süzgeci ("Yalnız" / "Gizli"): kip "dahil" (yalnız seçilenler) ya da "haric" (seçilenleri gizle).
 * Genel metin araması (`arama`, `metinUyar`) da burada. İkisi de TASKS ile MAP arasında ORTAK ve kişi başına
 * sunucuda saklanır (tercihDeposu.ts). TASKS'ta "Task adı ▾" sütun süzgeci ayrıca vardır (tabloSuzgec.ts).
 */

import { disariDinle } from '../../../cekirdek/ortak/disariKapat';
import { useEffect, useMemo, useRef, useState } from 'react';
import { DegerSecici } from './SuzgecMenusu';
import { degerListesi, type DegerSatiri } from './tabloSuzgec';
import type { IsSatir } from '../../../cekirdek/is/tipler';
import { katla } from '../../../cekirdek/ortak/ara';
import { KapatDugmesi } from '../../../cekirdek/ortak/Ilkel';
import { suzgecYaz, useTercih, type TurSuzgeci } from './tercihDeposu';

export type { TurSuzgeci } from './tercihDeposu';

export function turYaz(tur: TurSuzgeci) {
  suzgecYaz((s) => ({ ...s, tur }));
}
export function aramaYaz(arama: string) {
  suzgecYaz((s) => ({ ...s, arama }));
}

/** Tür süzgeci + genel arama (TASKS ↔ MAP ortak; kişi başına sunucuda, tercihDeposu.ts). */
export function useOrtakSuzgec() {
  const t = useTercih();
  return { tur: t.suzgec.tur, arama: t.suzgec.arama, turYaz, aramaYaz };
}

/** İşin tür etiketleri: task adı (+ varsa kategori). */
export function turlerOf(x: Pick<IsSatir, 'task_adi'> & { kategori?: string | null }): string[] {
  return [x.task_adi || '—', x.kategori].filter((v): v is string => Boolean(v));
}

export function turUyar(x: Pick<IsSatir, 'task_adi'> & { kategori?: string | null }, t: TurSuzgeci): boolean {
  if (!t.degerler.length) return true;
  const v = turlerOf(x);
  const var_ = v.some((d) => t.degerler.includes(d));
  return t.kip === 'dahil' ? var_ : !var_;
}

/** Düz metin arama (genel): iş alanlarının birleşimi. */
export function metinUyar(x: IsSatir, arama: string): boolean {
  const p = katla(arama).trim().split(/\s+/).filter(Boolean);
  if (!p.length) return true;
  const m = katla(
    [x.boss_task_no, x.is_no, x.musteri_no, x.musteri_adi, x.mahalle, x.ilce, x.kisa_adres, x.task_adi, x.atanan?.ad, x.boss_ekip, x.obek?.ad]
      .filter(Boolean)
      .join(' '),
  );
  return p.every((s) => m.includes(s));
}

/** Tür süzgecinin çip metni ("İş türü: yalnız TV Kurulum", "İş türü: yalnız 15 tür", "İş türü: gizli 3 tür");
 *  süzgeç yoksa null. TASKS ve MAP aynı metni gösterir. */
export function turEtiketi(tur: TurSuzgeci): string | null {
  const n = tur.degerler.length;
  return n ? `İş türü: ${tur.kip === 'dahil' ? 'yalnız' : 'gizli'} ${n === 1 ? tur.degerler[0] : `${n} tür`}` : null;
}

type TurIsi = Pick<IsSatir, 'task_adi'> & { kategori?: string | null };

/** İş türü süzgecinin değer listesi (bütün açık işlerin task adları, çoktan aza). */
export function turDegerleri(isler: TurIsi[], secili: readonly string[]): DegerSatiri[] {
  const t = isler.flatMap(turlerOf);
  return degerListesi(t, t, secili, 'sayi');
}

/** İş türü: sütun süzgeçleriyle AYNI bileşen (SuzgecMenusu.tsx DegerSecici); her değişiklik hemen uygulanır.
 *  Açılır pencerede (TASKS/MAP) ve MAP'in Filtreler çekmecesinde. */
export function TurSuzgecGovde({ isler, odakla = false }: { isler: TurIsi[]; odakla?: boolean }) {
  const { tur } = useOrtakSuzgec();
  const degerler = useMemo(() => turDegerleri(isler, tur.degerler), [isler, tur.degerler]);
  const secim = useMemo(() => new Set(tur.degerler), [tur.degerler]);
  return (
    <DegerSecici
      degerler={degerler}
      kip={tur.kip}
      setKip={(kip) => suzgecYaz((s) => ({ ...s, tur: { ...s.tur, kip } }))}
      secim={secim}
      setSecim={(f) => suzgecYaz((s) => ({ ...s, tur: { ...s.tur, degerler: [...f(new Set(s.tur.degerler))] } }))}
      odakla={odakla}
      araYazisi="Tür ara…"
    />
  );
}

/** Çip + açılır onay listesi (arama, Tümünü seç, Temizle, Dahil/Hariç). */
export function TurSuzgecDugmesi({ isler }: { isler: TurIsi[] }) {
  const { tur } = useOrtakSuzgec();
  const [acik, setAcik] = useState(false);
  const kok = useRef<HTMLDivElement>(null);
  useEffect(() => (acik ? disariDinle(kok, () => setAcik(false)) : undefined), [acik]);
  const etiket = turEtiketi(tur) ?? 'İş türü: tümü';
  const n = tur.degerler.length;
  return (
    <div className="ts-kok" ref={kok}>
      <button
        type="button"
        className={`o-suz-cip ts-cip${n ? ' etkin' : ''}`}
        aria-haspopup="dialog"
        aria-expanded={acik}
        onClick={() => setAcik((a) => !a)}
      >
        <span>{etiket}</span> <span aria-hidden="true">▾</span>
      </button>
      {n ? (
        <KapatDugmesi kucuk etiket="İş türü süzgecini kaldır" kapat={() => turYaz({ ...tur, degerler: [] })} />
      ) : null}
      {acik ? (
        <div className="ts-pencere" role="dialog" aria-label="İş türü süzgeci">
          <TurSuzgecGovde isler={isler} odakla />
        </div>
      ) : null}
    </div>
  );
}
