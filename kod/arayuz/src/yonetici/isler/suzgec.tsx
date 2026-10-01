/**
 * Süz (§6.1): tek "Süz" düğmesi; çekmecede İlçe, Task türü, Şerit, Teknisyen,
 * Kaynak ve "Yalnız: geciken · BTK · ticketlı · tekrar · randevusu bugün ·
 * BOSS'a işlenecek". Etkin süzgeçler aramanın yanında kaldırılabilir çip olur.
 * Arama: Task No, müşteri no, müşteri adı, mahalle, bina/kısa adres.
 */

import { useMemo } from 'react';
import type { IsSatir } from '../../is/tipler';
import { Panel } from '../../ortak/Panel';
import { Cip, CipSirasi, SuzCipi } from '../../ortak/Suz';
import { katla } from '../../ortak/ara';
import { gunAnahtari, kisaAd } from './parcalar';

export type Yalniz = 'geciken' | 'asan24' | 'btk' | 'btk48' | 'ticketli' | 'tekrar' | 'bugun_randevu' | 'boss_islenecek' | 'onerili';

export interface Suzgec {
  ilce: string[];
  task: string[];
  serit: string[];
  teknik: number[];
  kaynak: Array<'global' | 'bayi' | 'bos'>;
  yalniz: Yalniz[];
}

export const BOS_SUZGEC: Suzgec = { ilce: [], task: [], serit: [], teknik: [], kaynak: [], yalniz: [] };

export const YALNIZ_ETIKET: Record<Yalniz, string> = {
  geciken: 'Geciken',
  asan24: '24 saati aşan',
  btk: 'BTK',
  btk48: '48 saati aşan BTK',
  ticketli: 'Ticketlı',
  tekrar: 'Tekrar arıza',
  bugun_randevu: 'Randevusu bugün',
  boss_islenecek: 'BOSS’a işlenecek',
  onerili: 'Önerisi olan',
};

const SERIT_ETIKET: Record<string, string> = { BTK: 'BTK', SAHA: 'Saha', MASA: 'Masa', LOJISTIK: 'Lojistik' };
const KAYNAK_ETIKET: Record<string, string> = { global: 'Global', bayi: 'Bayi', bos: 'Kanal bilinmiyor' };

export function suzgecSayisi(s: Suzgec): number {
  return s.ilce.length + s.task.length + s.serit.length + s.teknik.length + s.kaynak.length + s.yalniz.length;
}

function kaynakKodu(x: IsSatir): 'global' | 'bayi' | 'bos' | null {
  if (x.kaynak === 'bayi' || x.kanal_grubu === 'dehanet' || x.kanal_grubu === 'diger_bayi') return 'bayi';
  if (x.kanal_grubu === 'global') return 'global';
  if (!x.kanal_grubu || x.kanal_grubu === 'bos') return 'bos';
  return null;
}

/** Arama metni: Task No, iş no, müşteri no/adı, mahalle, ilçe, kısa adres, task adı. */
export function aramaMetni(x: IsSatir): string {
  return katla(
    [x.boss_task_no, x.is_no, x.musteri_no, x.musteri_adi, x.mahalle, x.ilce, x.kisa_adres, x.task_adi, x.atanan?.ad, x.boss_ekip]
      .filter(Boolean)
      .join(' '),
  );
}

export function suz(isler: IsSatir[], s: Suzgec, arama: string, simdi: Date): IsSatir[] {
  const sorgu = katla(arama).trim().split(/\s+/).filter(Boolean);
  const bugun = gunAnahtari(simdi);
  const y48 = simdi.getTime() - 48 * 3600e3;
  const simdiMetin = `${bugun} ${String(simdi.getHours()).padStart(2, '0')}:${String(simdi.getMinutes()).padStart(2, '0')}`;
  return isler.filter((x) => {
    if (s.ilce.length && !s.ilce.includes(x.ilce ?? '')) return false;
    if (s.task.length && !s.task.includes(x.task_adi)) return false;
    if (s.serit.length && !s.serit.includes(x.serit)) return false;
    if (s.teknik.length && !s.teknik.includes(x.atanan?.id ?? x.oneri?.teknik.id ?? -1)) return false;
    if (s.kaynak.length) {
      const k = kaynakKodu(x);
      if (!k || !s.kaynak.includes(k)) return false;
    }
    for (const y of s.yalniz) {
      if (y === 'geciken' && !x.gecikti) return false;
      if (y === 'asan24' && !(x.son24 && x.son24 < simdiMetin)) return false;
      if (y === 'btk' && x.serit !== 'BTK') return false;
      if (y === 'btk48') {
        const a = Date.parse(x.acilis.replace(' ', 'T'));
        if (x.serit !== 'BTK' || !(a < y48)) return false;
      }
      if (y === 'ticketli' && !x.ticket && !x.binada_acik_ticket) return false;
      if (y === 'tekrar' && !x.rozetler.includes('tekrar')) return false;
      if (y === 'bugun_randevu' && !(x.randevu && x.randevu.bas.slice(0, 10) === bugun)) return false;
      if (y === 'boss_islenecek' && !x.rozetler.includes('boss_islenecek')) return false;
      if (y === 'onerili' && !x.oneri) return false;
    }
    if (sorgu.length) {
      const m = aramaMetni(x);
      if (!sorgu.every((p) => m.includes(p))) return false;
    }
    return true;
  });
}

/** Etkin süzgeç çipleri (aramanın yanında; ✕ ile kalkar). */
export function SuzgecCipleri({
  s,
  degisti,
  teknikAdi,
}: {
  s: Suzgec;
  degisti: (s: Suzgec) => void;
  teknikAdi: (id: number) => string;
}) {
  const cipler: Array<{ anahtar: string; etiket: string; kaldir: () => void }> = [];
  const cikar = <K extends keyof Suzgec>(alan: K, deger: Suzgec[K][number]) =>
    degisti({ ...s, [alan]: (s[alan] as Array<unknown>).filter((v) => v !== deger) } as Suzgec);
  s.yalniz.forEach((y) => cipler.push({ anahtar: `y${y}`, etiket: YALNIZ_ETIKET[y], kaldir: () => cikar('yalniz', y) }));
  s.ilce.forEach((v) => cipler.push({ anahtar: `i${v}`, etiket: v, kaldir: () => cikar('ilce', v) }));
  s.serit.forEach((v) => cipler.push({ anahtar: `s${v}`, etiket: SERIT_ETIKET[v] ?? v, kaldir: () => cikar('serit', v) }));
  s.task.forEach((v) => cipler.push({ anahtar: `t${v}`, etiket: v, kaldir: () => cikar('task', v) }));
  s.teknik.forEach((v) => cipler.push({ anahtar: `k${v}`, etiket: teknikAdi(v), kaldir: () => cikar('teknik', v) }));
  s.kaynak.forEach((v) => cipler.push({ anahtar: `n${v}`, etiket: KAYNAK_ETIKET[v], kaldir: () => cikar('kaynak', v) }));
  if (!cipler.length) return null;
  return (
    <div className="ip-suz-cipleri" aria-label="Etkin süzgeçler">
      {cipler.map((c) => (
        <SuzCipi key={c.anahtar} kaldir={c.kaldir}>
          {c.etiket}
        </SuzCipi>
      ))}
      <button type="button" className="o-bag" onClick={() => degisti(BOS_SUZGEC)}>
        Hepsini kaldır
      </button>
    </div>
  );
}

function degistir<T>(liste: T[], deger: T): T[] {
  return liste.includes(deger) ? liste.filter((x) => x !== deger) : [...liste, deger];
}

export function SuzgecCekmecesi({
  acik,
  kapat,
  s,
  degisti,
  isler,
}: {
  acik: boolean;
  kapat: () => void;
  s: Suzgec;
  degisti: (s: Suzgec) => void;
  isler: IsSatir[];
}) {
  const secenek = useMemo(() => {
    const say = <K,>(f: (x: IsSatir) => K | null | undefined) => {
      const m = new Map<K, number>();
      isler.forEach((x) => {
        const v = f(x);
        if (v !== null && v !== undefined && v !== '') m.set(v, (m.get(v) ?? 0) + 1);
      });
      return [...m.entries()].sort((a, b) => b[1] - a[1]);
    };
    const teknik = new Map<number, { ad: string; n: number }>();
    isler.forEach((x) => {
      const k = x.atanan ?? x.oneri?.teknik;
      if (k) teknik.set(k.id, { ad: k.ad, n: (teknik.get(k.id)?.n ?? 0) + 1 });
    });
    return {
      ilce: say((x) => x.ilce),
      task: say((x) => x.task_adi),
      serit: say((x) => x.serit),
      kaynak: say((x) => kaynakKodu(x)),
      teknik: [...teknik.entries()].sort((a, b) => a[1].ad.localeCompare(b[1].ad, 'tr')),
    };
  }, [isler]);

  return (
    <Panel
      acik={acik}
      kapat={kapat}
      baslik="Süz"
      altBaslik="Seçtikleriniz listenin üstünde çip olarak görünür."
      alt={
        <>
          <button type="button" className="o-dugme metin" onClick={() => degisti(BOS_SUZGEC)}>
            Temizle
          </button>
          <span className="bosluk" />
          <button type="button" className="o-dugme" onClick={kapat}>
            Tamam
          </button>
        </>
      }
    >
      <div className="ip-suzgec">
        <section>
          <h3>Yalnız</h3>
          <CipSirasi etiket="Yalnız">
            {(Object.keys(YALNIZ_ETIKET) as Yalniz[]).map((y) => (
              <Cip key={y} secili={s.yalniz.includes(y)} onClick={() => degisti({ ...s, yalniz: degistir(s.yalniz, y) })}>
                {YALNIZ_ETIKET[y]}
              </Cip>
            ))}
          </CipSirasi>
        </section>
        <section>
          <h3>Şerit</h3>
          <CipSirasi etiket="Şerit">
            {secenek.serit.map(([v, n]) => (
              <Cip key={v} sayi={n} secili={s.serit.includes(v)} onClick={() => degisti({ ...s, serit: degistir(s.serit, v) })}>
                {SERIT_ETIKET[v] ?? v}
              </Cip>
            ))}
          </CipSirasi>
        </section>
        <section>
          <h3>Kaynak</h3>
          <CipSirasi etiket="Kaynak">
            {secenek.kaynak.map(([v, n]) => (
              <Cip key={v} sayi={n} secili={s.kaynak.includes(v)} onClick={() => degisti({ ...s, kaynak: degistir(s.kaynak, v) })}>
                {KAYNAK_ETIKET[v]}
              </Cip>
            ))}
          </CipSirasi>
        </section>
        <section>
          <h3>İlçe</h3>
          <div className="ip-suz-sarmal">
            {secenek.ilce.map(([v, n]) => (
              <Cip key={v} sayi={n} secili={s.ilce.includes(v)} onClick={() => degisti({ ...s, ilce: degistir(s.ilce, v) })}>
                {v}
              </Cip>
            ))}
          </div>
        </section>
        <section>
          <h3>Task türü</h3>
          <div className="ip-suz-sarmal">
            {secenek.task.map(([v, n]) => (
              <Cip key={v} sayi={n} secili={s.task.includes(v)} onClick={() => degisti({ ...s, task: degistir(s.task, v) })}>
                {v}
              </Cip>
            ))}
          </div>
        </section>
        {secenek.teknik.length ? (
          <section>
            <h3>Teknisyen (atanan ya da önerilen)</h3>
            <div className="ip-suz-sarmal">
              {secenek.teknik.map(([id, t]) => (
                <Cip key={id} sayi={t.n} secili={s.teknik.includes(id)} onClick={() => degisti({ ...s, teknik: degistir(s.teknik, id) })}>
                  {kisaAd(t.ad)}
                </Cip>
              ))}
            </div>
          </section>
        ) : null}
      </div>
    </Panel>
  );
}
