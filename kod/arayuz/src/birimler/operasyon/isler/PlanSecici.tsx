/**
 * Planla bölümünün iki seçicisi:
 *   · TeknikAcilir — aranabilir açılır liste (serbest yazı yok). Uygulamanın
 *     teknisyenleri + `GET /api/boss/ekipler`; BOSS teknisyeni uygulamadaki bir
 *     kişiye (boss_ekip adı) eşliyse o kişi seçilir, değilse "eşleşmemiş" görünür.
 *   · TakvimDilim — ay ızgarası (gün) + saat dilimi + "Müşteriyle konuşuldu".
 */

import { disariDinle } from '../../../cekirdek/ortak/disariKapat';
import { useEffect, useMemo, useRef, useState } from 'react';
import type { TeknikOzet } from '../../../cekirdek/is/tipler';
import { bossEkipleri } from '../../../cekirdek/is/api';
import type { Dilim } from '../../../cekirdek/ortak/DilimSecici';
import { katla } from '../../../cekirdek/ortak/ara';
import { SimgeDugme } from '../../../cekirdek/ortak/Ilkel';
import { Geri, Ileri } from '../../../cekirdek/ortak/Ikon';

let BOSS_ONBELLEK: Promise<Array<{ id: string | number; ad: string; aktif?: boolean }>> | null = null;

interface Satir {
  anahtar: string;
  id: number | null;
  ad: string;
  /** Alt satır: "Önerilen · BOSS: …". */
  bilgi: string;
  /** Sağ sütundaki yük rozeti: "bugün 1 iş". */
  yuk: string;
}

export function TeknikAcilir({
  teknikler,
  deger,
  degisti,
  onerilen,
}: {
  teknikler: TeknikOzet[];
  deger: number | null;
  degisti: (id: number) => void;
  onerilen?: number | null;
}) {
  const [boss, setBoss] = useState<Array<{ id: string | number; ad: string; aktif?: boolean }>>([]);
  const [acik, setAcik] = useState(false);
  const [sorgu, setSorgu] = useState('');
  const kok = useRef<HTMLDivElement>(null);

  useEffect(() => {
    BOSS_ONBELLEK ??= bossEkipleri().catch(() => []);
    let canli = true;
    void BOSS_ONBELLEK.then((l) => canli && setBoss(l));
    return () => {
      canli = false;
    };
  }, []);

  useEffect(() => (acik ? disariDinle(kok, () => setAcik(false), { esc: false }) : undefined), [acik]);

  const satirlar = useMemo<Satir[]>(() => {
    const l: Satir[] = teknikler.map((t) => ({
      anahtar: `u${t.id}`,
      id: t.id,
      ad: t.ad,
      bilgi: [t.id === onerilen ? 'Önerilen' : '', t.boss_ekip && katla(t.boss_ekip) !== katla(t.ad) ? `BOSS: ${t.boss_ekip}` : '']
        .filter(Boolean)
        .join(' · '),
      yuk: t.bugun_yok ? 'bugün yok' : `bugün ${t.bugun.atanan} iş`,
    }));
    const esli = new Set(teknikler.map((t) => katla(t.boss_ekip ?? '')).filter(Boolean));
    boss
      .filter((b) => b.aktif !== false && !esli.has(katla(b.ad)))
      .forEach((b) => l.push({ anahtar: `b${b.id}`, id: null, ad: b.ad, bilgi: 'BOSS ekibi · uygulamada eşleşmemiş', yuk: '' }));
    return l;
  }, [teknikler, boss, onerilen]);

  const s = katla(sorgu).trim();
  const gorunen = s ? satirlar.filter((r) => katla(`${r.ad} ${r.bilgi}`).includes(s)) : satirlar;
  const secili = teknikler.find((t) => t.id === deger);

  return (
    <div className="ps-acilir" ref={kok}>
      <button type="button" className="ps-dugme o-girdi" aria-haspopup="listbox" aria-expanded={acik} onClick={() => setAcik((a) => !a)}>
        <span className="ps-ad">{secili ? secili.ad : 'Teknisyen seçin'}</span>
        <span aria-hidden="true">▾</span>
      </button>
      {acik ? (
        <div className="ps-liste">
          <input
            className="o-girdi"
            type="search"
            autoFocus
            value={sorgu}
            placeholder="Ara…"
            aria-label="Teknisyen ara"
            onChange={(o) => setSorgu(o.target.value)}
          />
          <div role="listbox" className="ps-secenekler">
            {gorunen.length ? (
              gorunen.map((r) => (
                <button
                  key={r.anahtar}
                  type="button"
                  role="option"
                  aria-selected={r.id !== null && r.id === deger}
                  disabled={r.id === null}
                  className={r.id !== null && r.id === deger ? 'secili' : undefined}
                  onClick={() => {
                    if (r.id === null) return;
                    degisti(r.id);
                    setAcik(false);
                    setSorgu('');
                  }}
                >
                  <span className="ps-ad" title={r.ad}>{r.ad}</span>
                  {r.yuk ? <span className="ps-yuk">{r.yuk}</span> : <span />}
                  {r.bilgi ? <span className="ps-alt">{r.bilgi}</span> : null}
                </button>
              ))
            ) : (
              <p className="ip-sessiz">Bu adla teknisyen yok.</p>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}

/* ------------------------------ takvim ------------------------------ */

const AYLAR = ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran', 'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık'];
const iki = (n: number) => String(n).padStart(2, '0');
const anahtarOf = (d: Date) => `${d.getFullYear()}-${iki(d.getMonth() + 1)}-${iki(d.getDate())}`;

export function TakvimDilim({
  deger,
  degisti,
  ilkSaat,
  sonSaat,
  simdi,
  enCokGun = 7,
}: {
  deger: Dilim | null;
  degisti: (d: Dilim | null) => void;
  ilkSaat: number;
  sonSaat: number;
  simdi: Date;
  enCokGun?: number;
}) {
  const bugun = anahtarOf(simdi);
  const sinir = anahtarOf(new Date(simdi.getFullYear(), simdi.getMonth(), simdi.getDate() + enCokGun));
  const [bosGun, setBosGun] = useState(bugun);
  const gun = deger ? deger.bas.slice(0, 10) : bosGun;
  const [ay, setAy] = useState(() => new Date(Number(gun.slice(0, 4)), Number(gun.slice(5, 7)) - 1, 1));

  const hucreler = useMemo(() => {
    const ilk = new Date(ay.getFullYear(), ay.getMonth(), 1);
    const kayma = (ilk.getDay() + 6) % 7; // Pazartesi başlar
    const gunSayisi = new Date(ay.getFullYear(), ay.getMonth() + 1, 0).getDate();
    const l: Array<string | null> = Array.from({ length: kayma }, () => null);
    for (let i = 1; i <= gunSayisi; i++) l.push(anahtarOf(new Date(ay.getFullYear(), ay.getMonth(), i)));
    return l;
  }, [ay]);

  const dilimler = useMemo(() => {
    const l: Array<{ bas: number; bit: number }> = [];
    for (let s = ilkSaat; s + 2 <= sonSaat; s += 2) l.push({ bas: s, bit: s + 2 });
    return l;
  }, [ilkSaat, sonSaat]);

  const gunSec = (a: string) => {
    setBosGun(a);
    if (deger) {
      const saat = Number(deger.bit.slice(11, 13));
      if (a === bugun && saat <= simdi.getHours()) degisti(null);
      else degisti({ ...deger, bas: `${a}${deger.bas.slice(10)}`, bit: `${a}${deger.bit.slice(10)}` });
    }
  };

  const ayKaydir = (n: number) => setAy((a) => new Date(a.getFullYear(), a.getMonth() + n, 1));
  const oncekiYok = ay.getFullYear() === simdi.getFullYear() && ay.getMonth() <= simdi.getMonth();

  return (
    <div className="ps-takvim-kok">
      <div className="ps-takvim">
        <div className="ps-ay">
          <SimgeDugme kucuk etiket="Önceki ay" onClick={() => ayKaydir(-1)} disabled={oncekiYok}>
            <Geri boyut={14} />
          </SimgeDugme>
          <b>
            {AYLAR[ay.getMonth()]} {ay.getFullYear()}
          </b>
          <SimgeDugme kucuk etiket="Sonraki ay" onClick={() => ayKaydir(1)}>
            <Ileri boyut={14} />
          </SimgeDugme>
        </div>
        <div className="ps-izgara" role="grid">
          {['Pt', 'Sa', 'Ça', 'Pe', 'Cu', 'Ct', 'Pz'].map((g) => (
            <span key={g} className="ps-gunadi">
              {g}
            </span>
          ))}
          {hucreler.map((h, i) =>
            h ? (
              <button
                key={h}
                type="button"
                className={`ps-gun${h === gun ? ' secili' : ''}${h === bugun ? ' bugun' : ''}`}
                disabled={h < bugun || h > sinir}
                aria-pressed={h === gun}
                onClick={() => gunSec(h)}
              >
                {Number(h.slice(8))}
              </button>
            ) : (
              <span key={`b${i}`} />
            ),
          )}
        </div>
      </div>
      <div className="ps-saatler" role="group" aria-label="Saat aralığı">
        {dilimler.map((d) => {
          const bas = `${gun} ${iki(d.bas)}:00:00`;
          const bit = `${gun} ${iki(d.bit)}:00:00`;
          const gecmis = gun === bugun && d.bit <= simdi.getHours();
          const secili = deger?.bas === bas && deger?.bit === bit;
          return (
            <button
              key={d.bas}
              type="button"
              className={`ps-saat${secili ? ' secili' : ''}`}
              disabled={gecmis}
              aria-pressed={secili}
              onClick={() => degisti(secili ? null : { bas, bit, teyitli: deger?.teyitli ?? false })}
            >
              {iki(d.bas)}–{iki(d.bit)}
            </button>
          );
        })}
      </div>
      <label className="o-onay-kutusu">
        <input
          type="checkbox"
          checked={Boolean(deger?.teyitli)}
          disabled={!deger}
          onChange={(o) => deger && degisti({ ...deger, teyitli: o.target.checked })}
        />
        <span>Müşteriyle konuşuldu, saat teyitli</span>
      </label>
    </div>
  );
}
