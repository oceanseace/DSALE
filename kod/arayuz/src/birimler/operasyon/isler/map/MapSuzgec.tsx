/**
 * MAP süzgeçleri — TASKS ile AYNI süzgeç durumu (tercihDeposu.ts; kişi başına sunucuda):
 *   · `MapSuzgecCubugu` tek ince şerit: "Filtreler (N)" düğmesi + etkin süzgeç çipleri ("Task adı: 3 değer ✕",
 *     "Geliş: son 7 gün ✕", "+2"); haritayı örtmez.
 *   · `MapFiltreCekmecesi` sağdan çekmece (perdesiz; harita gezilebilir): Ara · Özel filtre · Geliş tarihi ·
 *     İş türü (Yalnız/Gizli) · her sütun İş türü ile AYNI arayüzde (kip, arama, Görünenleri seç / Temizle, sayılar;
 *     değişiklik hemen uygulanır — SuzgecMenusu.tsx SuzgecGovde `aninda`).
 * Çip listesi `useEtkinCipler` ile kurulur (TASKS'takiyle aynı adlar). Kim: IsHaritasiEkrani.tsx.
 */

import { useMemo, useState } from 'react';
import { Panel } from '../../../../cekirdek/ortak/Panel';
import { Kapat } from '../../../../cekirdek/ortak/Ikon';
import { eslesir } from '../../../../cekirdek/ortak/ara';
import type { IsSatir } from '../../../../cekirdek/is/tipler';
import { GorunumSecici, type GorunumDepo } from '../Gorunumler';
import { TurSuzgecGovde, turEtiketi, useOrtakSuzgec } from '../isTuru';
import { SuzgecGovde } from '../SuzgecMenusu';
import type { Sutun } from '../sutunlar';
import { cipIpucu, cipKisalt, cipMetni, type TabloSuzgec } from '../tabloSuzgec';
import { TARIH_TUMU, TarihSuzgecDugmesi, tarihEtiketi, tarihEtkin, type TarihSuzgeci } from './tarihSuzgeci';
import '../tablo.css';

export interface Cip {
  anahtar: string;
  metin: string;
  ipucu?: string;
  kaldir: () => void;
}

/** Etkin süzgeçlerin çipleri (sıra: Özel filtre · Ara · tür · tarih · sütunlar). */
export function useEtkinCipler(
  g: GorunumDepo,
  t: TabloSuzgec,
  tarih: TarihSuzgeci,
  setTarih: (s: TarihSuzgeci) => void,
  bugun: string,
): Cip[] {
  const ortak = useOrtakSuzgec();
  return useMemo(() => {
    const l: Cip[] = [];
    if (g.secili) l.push({ anahtar: 'gorunum', metin: `Özel filtre: ${g.secili.ad}`, kaldir: () => g.sec(null) });
    if (ortak.arama) l.push({ anahtar: 'ara', metin: `Ara: ${ortak.arama}`, kaldir: () => ortak.aramaYaz('') });
    const te = turEtiketi(ortak.tur);
    if (te)
      l.push({ anahtar: 'tur', metin: te, ipucu: ortak.tur.degerler.join(', '), kaldir: () => ortak.turYaz({ ...ortak.tur, degerler: [] }) });
    if (tarihEtkin(tarih)) l.push({ anahtar: 'tarih', metin: tarihEtiketi(tarih, bugun), kaldir: () => setTarih(TARIH_TUMU) });
    t.etkin.forEach((e) => {
      const b = t.sutun.get(e.id)?.baslik ?? e.id;
      l.push({ anahtar: e.id, metin: cipMetni(b, e.f), ipucu: cipIpucu(b, e.f), kaldir: () => t.sutunYaz(e.id, null) });
    });
    return l;
  }, [g, ortak, tarih, setTarih, bugun, t]);
}

const CIP_EN_COK = 3;

export function MapSuzgecCubugu({ cipler, ac, temizle }: { cipler: Cip[]; ac: () => void; temizle: () => void }) {
  const gorunen = cipler.slice(0, CIP_EN_COK);
  const kalan = cipler.length - gorunen.length;
  return (
    <div className="ih-kutu mp-cubuk" role="toolbar" aria-label="MAP süzgeçleri">
      <button type="button" className={`mp-filtre-dugme${cipler.length ? ' etkin' : ''}`} onClick={ac} aria-haspopup="dialog">
        Filtreler{cipler.length ? ` (${cipler.length})` : ''}
      </button>
      {gorunen.map((c) => (
        <span key={c.anahtar} className="xg-cip" title={c.ipucu ?? c.metin}>
          <span className="xg-cip-metin">{cipKisalt(c.metin)}</span>
          <button type="button" aria-label={`${c.metin} — kaldır`} title="Kaldır" onClick={c.kaldir}>
            <Kapat boyut={12} kalinlik={2} />
          </button>
        </span>
      ))}
      {kalan > 0 ? (
        <button type="button" className="mp-arti" onClick={ac} title={cipler.slice(CIP_EN_COK).map((c) => c.metin).join('\n')}>
          +{kalan}
        </button>
      ) : null}
      {cipler.length > 1 ? (
        <button type="button" className="mp-temizle" onClick={temizle}>
          Temizle
        </button>
      ) : null}
    </div>
  );
}

/** Sağdan çekmece: TASKS'taki bütün süzgeçler. Sütun süzgeci açılınca TASKS'taki ▾ menüsünün gövdesi gelir. */
export function MapFiltreCekmecesi({
  acik,
  kapat,
  g,
  t,
  sutunlar,
  oncelikli,
  tarih,
  setTarih,
  bugun,
  isler,
  cipler,
  gosterilen,
  toplam,
  temizle,
}: {
  acik: boolean;
  kapat: () => void;
  g: GorunumDepo;
  t: TabloSuzgec;
  sutunlar: Sutun[];
  /** TASKS'ta görünen sütun kimlikleri (önce bunlar listelenir). */
  oncelikli: string[];
  tarih: TarihSuzgeci;
  setTarih: (s: TarihSuzgeci) => void;
  bugun: string;
  isler: IsSatir[];
  cipler: Cip[];
  gosterilen: number;
  toplam: number;
  temizle: () => void;
}) {
  const ortak = useOrtakSuzgec();
  const [sutunAra, setSutunAra] = useState('');
  const [acikSutun, setAcikSutun] = useState<string | null>(null);
  const [hepsi, setHepsi] = useState(false);

  const sirali = useMemo(() => {
    const etkin = new Set(t.etkin.map((e) => e.id));
    const on = new Set(oncelikli);
    const puan = (c: Sutun) => (etkin.has(c.id) ? 0 : on.has(c.id) ? 1 : 2);
    const l = sutunlar.filter((c) => c.id !== 'renk' || etkin.has(c.id));
    return l
      .map((c, i) => ({ c, i }))
      .sort((a, b) => puan(a.c) - puan(b.c) || (puan(a.c) === 1 ? oncelikli.indexOf(a.c.id) - oncelikli.indexOf(b.c.id) : a.i - b.i))
      .map((x) => x.c);
  }, [sutunlar, oncelikli, t.etkin]);
  const aranan = sutunAra.trim() ? sirali.filter((c) => eslesir(c.baslik, sutunAra)) : sirali;
  const etkinSayi = t.etkin.length;
  const kisa = !hepsi && !sutunAra.trim() ? aranan.filter((c) => t.suzgec[c.id] || oncelikli.includes(c.id)) : aranan;

  return (
    <Panel
      acik={acik}
      kapat={kapat}
      perdesiz
      genislik={380}
      baslik="Filtreler"
      altBaslik={`Gösterilen ${gosterilen.toLocaleString('tr-TR')} / ${toplam.toLocaleString('tr-TR')} · TASKS ile ortak`}
      alt={
        <div className="mp-cekmece-alt">
          <button type="button" className="o-dugme" disabled={!cipler.length} onClick={temizle}>
            Tümünü temizle{cipler.length ? ` (${cipler.length})` : ''}
          </button>
          <button type="button" className="o-dugme vurgu" onClick={kapat}>
            Tamam
          </button>
        </div>
      }
    >
      <div className="mp-cekmece">
        <label className="mp-alan">
          <span>Ara</span>
          <input
            className="o-girdi"
            type="search"
            value={ortak.arama}
            placeholder="ad, Task No, mahalle…"
            onChange={(o) => ortak.aramaYaz(o.target.value)}
          />
        </label>
        <div className="mp-alan-satir">
          <GorunumSecici g={g} />
          <TarihSuzgecDugmesi deger={tarih} degisti={setTarih} bugun={bugun} />
        </div>
        <details className="mp-bolum">
          <summary>
            İş türü <span className="mp-ozet">{turEtiketi(ortak.tur)?.replace(/^İş türü: /, '') ?? 'tümü'}</span>
          </summary>
          <div className="mp-tur">
            <TurSuzgecGovde isler={isler} />
          </div>
        </details>
        <div className="mp-bolum-baslik">
          Sütunlar{etkinSayi ? <span className="mp-ozet"> · {etkinSayi} etkin</span> : null}
        </div>
        <input
          className="o-girdi kucuk"
          type="search"
          value={sutunAra}
          placeholder={`Sütun ara (${sutunlar.length})…`}
          onChange={(o) => setSutunAra(o.target.value)}
        />
        <div className="mp-sutunlar">
          {kisa.map((c) => {
            const f = t.suzgec[c.id];
            const acikMi = acikSutun === c.id;
            return (
              <div key={c.id} className={`mp-sutun${f ? ' etkin' : ''}${acikMi ? ' acik' : ''}`}>
                <button type="button" className="mp-sutun-bas" aria-expanded={acikMi} onClick={() => setAcikSutun(acikMi ? null : c.id)}>
                  <span className="ad">{c.baslik}</span>
                  <span className="mp-ozet">{f ? cipMetni('', f).replace(/^: /, '') : ''}</span>
                  <span aria-hidden="true">{acikMi ? '▴' : '▾'}</span>
                </button>
                {acikMi ? (
                  <div className="mp-sutun-govde xg-suzgec">
                    <SuzgecGovde key={c.id} id={c.id} t={t} kapat={() => setAcikSutun(null)} odakla aninda />
                  </div>
                ) : null}
              </div>
            );
          })}
          {!kisa.length ? <p className="ip-sessiz">Sütun bulunamadı.</p> : null}
        </div>
        {!hepsi && !sutunAra.trim() && kisa.length < aranan.length ? (
          <button type="button" className="o-dugme kucuk metin" onClick={() => setHepsi(true)}>
            Tüm sütunlar ({aranan.length})
          </button>
        ) : null}
      </div>
    </Panel>
  );
}
