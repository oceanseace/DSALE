/**
 * MAP tarih süzgeci: işin geliş tarihine (acilis) göre "şu tarihten önce", "şu tarihten sonra", "aralık"
 * (takvimle) ve hızlı seçimler (bugün · son 7 gün · 30 günden eski).
 * Giriş: useTarihSuzgeci() durum · tarihUyari(s) süzme işlevi · TarihSuzgecDugmesi çip + pencere.
 * Çağıran: IsHaritasiEkrani, Isler.tsx (çip), map/MapSuzgec.tsx. Seçim TASKS ↔ MAP ortak, kişi başına sunucuda.
 */

import { disariDinle } from '../../../../cekirdek/ortak/disariKapat';
import { useEffect, useRef, useState, type ChangeEvent } from 'react';
import { TARIH_BOS, suzgecYaz, useTercih, type TarihKipi, type TarihSuzgeci } from '../tercihDeposu';
import { gunAnahtari } from '../parcalar';
import { KapatDugmesi } from '../../../../cekirdek/ortak/Ilkel';

export type { TarihKipi, TarihSuzgeci } from '../tercihDeposu';
type Hazir = NonNullable<TarihSuzgeci['hazir']>;

export const TARIH_TUMU: TarihSuzgeci = TARIH_BOS;

const HAZIR_AD: Record<Hazir, string> = { bugun: 'Bugün', son7: 'Son 7 gün', eski30: '30 günden eski' };

/** "2026-10-06" + n gün. */
export function gunEkle(gun: string, n: number): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(gun);
  if (!m) return gun;
  return gunAnahtari(new Date(+m[1], +m[2] - 1, +m[3] + n));
}

/** "06.10" (bu yıl) · "06.10.2025" (başka yıl). */
function kisaGun(gun: string, bugun: string): string {
  const [y, a, g] = gun.split('-');
  if (!g) return gun;
  return y === bugun.slice(0, 4) ? `${g}.${a}` : `${g}.${a}.${y}`;
}

function hazirSecim(h: Hazir, bugun: string): TarihSuzgeci {
  if (h === 'bugun') return { ...TARIH_TUMU, kip: 'aralik', bas: bugun, bit: bugun, hazir: h };
  if (h === 'son7') return { ...TARIH_TUMU, kip: 'aralik', bas: gunEkle(bugun, -6), bit: bugun, hazir: h };
  return { ...TARIH_TUMU, kip: 'once', gun: gunEkle(bugun, -30), hazir: h };
}

/**
 * Süzme işlevi: işin açılış zamanı ("AAAA-AA-GG SS:DD:ss") seçime uyuyor mu.
 * Önce: seçilen gün DAHİL DEĞİL · sonra: seçilen gün dahil · aralık: iki uç dahil. Boş tarih sınır koymaz.
 */
export function tarihUyari(s: TarihSuzgeci): (acilis: string | null | undefined) => boolean {
  let alt = '';
  let ust = '';
  if (s.kip === 'once' && s.gun) ust = gunEkle(s.gun, -1);
  else if (s.kip === 'sonra' && s.gun) alt = s.gun;
  else if (s.kip === 'aralik') {
    const [a, b] = s.bas && s.bit && s.bas > s.bit ? [s.bit, s.bas] : [s.bas, s.bit];
    alt = a;
    ust = b;
  }
  if (!alt && !ust) return () => true;
  return (acilis) => {
    const g = String(acilis ?? '').slice(0, 10);
    if (g.length !== 10) return false;
    return (!alt || g >= alt) && (!ust || g <= ust);
  };
}

/** Çipte görünen ad: "Geliş: son 7 gün", "Geliş: 06.09 öncesi", "Geliş: 01.10–06.10". */
export function tarihEtiketi(s: TarihSuzgeci, bugun: string): string {
  if (s.hazir) return `Geliş: ${HAZIR_AD[s.hazir].toLocaleLowerCase('tr-TR')}`;
  if (s.kip === 'once' && s.gun) return `Geliş: ${kisaGun(s.gun, bugun)} öncesi`;
  if (s.kip === 'sonra' && s.gun) return `Geliş: ${kisaGun(s.gun, bugun)} ve sonrası`;
  if (s.kip === 'aralik' && (s.bas || s.bit)) {
    const [a, b] = s.bas && s.bit && s.bas > s.bit ? [s.bit, s.bas] : [s.bas, s.bit];
    if (a && b && a === b) return `Geliş: ${kisaGun(a, bugun)}`;
    return `Geliş: ${a ? kisaGun(a, bugun) : '…'}–${b ? kisaGun(b, bugun) : '…'}`;
  }
  return 'Geliş tarihi: tümü';
}

export function tarihEtkin(s: TarihSuzgeci): boolean {
  return s.kip === 'once' || s.kip === 'sonra' ? Boolean(s.gun) : s.kip === 'aralik' ? Boolean(s.bas || s.bit) : false;
}

/** Geliş tarihi süzgeci TASKS ↔ MAP ortak süzgecin parçası (kişi başına sunucuda, tercihDeposu.ts). */
export function useTarihSuzgeci(): [TarihSuzgeci, (s: TarihSuzgeci) => void] {
  const s = useTercih().suzgec.tarih;
  return [s, tarihYaz];
}
export function tarihYaz(t: TarihSuzgeci) {
  suzgecYaz((o) => ({ ...o, tarih: t }));
}

/** Çip + açılır pencere (Excel süzgeci gibi: seçim anında uygulanır). */
export function TarihSuzgecDugmesi({
  deger,
  degisti,
  bugun,
}: {
  deger: TarihSuzgeci;
  degisti: (s: TarihSuzgeci) => void;
  /** Bugünün günü (AAAA-AA-GG), sunucu saatine göre. */
  bugun: string;
}) {
  const [acik, setAcik] = useState(false);
  const kok = useRef<HTMLDivElement>(null);

  useEffect(() => (acik ? disariDinle(kok, () => setAcik(false)) : undefined), [acik]);

  const etkin = tarihEtkin(deger);
  const kipSec = (kip: TarihKipi) => {
    if (kip === 'hepsi') return degisti(TARIH_TUMU);
    const gun = deger.gun || gunEkle(bugun, kip === 'once' ? -30 : -7);
    degisti({
      ...deger,
      kip,
      gun,
      bas: deger.bas || gunEkle(bugun, -7),
      bit: deger.bit || bugun,
      hazir: null,
    });
  };
  const yaz = (alan: 'gun' | 'bas' | 'bit', kip: TarihKipi) => (o: ChangeEvent<HTMLInputElement>) =>
    degisti({ ...deger, kip, [alan]: o.target.value, hazir: null });
  const not =
    deger.kip === 'once'
      ? 'Seçilen gün dahil değil.'
      : deger.kip === 'sonra'
        ? 'Seçilen gün dahil.'
        : deger.kip === 'aralik'
          ? 'İki gün de dahil.'
          : 'Bütün açık işler gösteriliyor.';

  return (
    <div className="ts-kok" ref={kok}>
      <button
        type="button"
        className={`o-suz-cip ts-cip${etkin ? ' etkin' : ''}`}
        aria-haspopup="dialog"
        aria-expanded={acik}
        title="İşin BOSS'a geliş tarihine göre süz"
        onClick={() => setAcik((a) => !a)}
      >
        <span>{tarihEtiketi(deger, bugun)}</span> <span aria-hidden="true">▾</span>
      </button>
      {etkin ? (
        <KapatDugmesi kucuk etiket="Tarih süzgecini kaldır" kapat={() => degisti(TARIH_TUMU)} />
      ) : null}
      {acik ? (
        <div className="ts-pencere mp-tarih" role="dialog" aria-label="Geliş tarihi süzgeci">
          <div className="mp-tarih-baslik">Geliş tarihi</div>
          <div className="mp-hizli" role="group" aria-label="Hızlı seçim">
            {(Object.keys(HAZIR_AD) as Hazir[]).map((h) => (
              <button
                key={h}
                type="button"
                className={deger.hazir === h ? 'secili' : undefined}
                aria-pressed={deger.hazir === h}
                onClick={() => degisti(hazirSecim(h, bugun))}
              >
                {HAZIR_AD[h]}
              </button>
            ))}
          </div>
          <div className="mp-tarih-kipler" role="radiogroup" aria-label="Süzme biçimi">
            <label>
              <input type="radio" name="mp-tarih-kip" checked={deger.kip === 'hepsi'} onChange={() => kipSec('hepsi')} /> Tümü
            </label>
            <label>
              <input type="radio" name="mp-tarih-kip" checked={deger.kip === 'once'} onChange={() => kipSec('once')} /> Şu tarihten önce
            </label>
            {deger.kip === 'once' ? (
              <input type="date" className="o-girdi mp-gun" value={deger.gun} onChange={yaz('gun', 'once')} aria-label="Bu günden önce gelenler" />
            ) : null}
            <label>
              <input type="radio" name="mp-tarih-kip" checked={deger.kip === 'sonra'} onChange={() => kipSec('sonra')} /> Şu tarihten sonra
            </label>
            {deger.kip === 'sonra' ? (
              <input type="date" className="o-girdi mp-gun" value={deger.gun} onChange={yaz('gun', 'sonra')} aria-label="Bu günden sonra gelenler" />
            ) : null}
            <label>
              <input type="radio" name="mp-tarih-kip" checked={deger.kip === 'aralik'} onChange={() => kipSec('aralik')} /> Aralık
            </label>
            {deger.kip === 'aralik' ? (
              <div className="mp-aralik">
                <input type="date" className="o-girdi mp-gun" value={deger.bas} onChange={yaz('bas', 'aralik')} aria-label="Aralık başı" />
                <span aria-hidden="true">–</span>
                <input type="date" className="o-girdi mp-gun" value={deger.bit} onChange={yaz('bit', 'aralik')} aria-label="Aralık sonu" />
              </div>
            ) : null}
          </div>
          <p className="mp-tarih-not">{not}</p>
        </div>
      ) : null}
    </div>
  );
}
