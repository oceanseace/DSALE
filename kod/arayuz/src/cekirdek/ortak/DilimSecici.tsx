/**
 * Dilim seçici: randevu için gün çipleri + 2 saatlik dilim çipleri + teyit
 * kutusu (§7.3). Klavye gerekmez; iki dokunuş ve bir işaretle randevu hazır.
 *
 * Değer sunucunun zaman biçimindedir ("AAAA-AA-GG SS:DD:00"); geçmiş dilim
 * seçilemez. Sunucu kuralları (en çok 4 saat, en çok 7 gün ileri) burada da
 * uygulanır ama son söz sunucunundur.
 */

import { useMemo, useState } from 'react';
import { Cip, CipSirasi } from './Suz';
import './bilesen.css';

export interface Dilim {
  bas: string;
  bit: string;
  teyitli: boolean;
}

const GUNLER = ['Pazar', 'Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi'];

function iki(n: number) {
  return String(n).padStart(2, '0');
}

function gunAnahtari(d: Date) {
  return `${d.getFullYear()}-${iki(d.getMonth() + 1)}-${iki(d.getDate())}`;
}

export function DilimSecici({
  deger,
  degisti,
  gunSayisi = 7,
  ilkSaat = 8,
  sonSaat = 20,
  simdi,
  teyitGoster = true,
}: {
  deger: Dilim | null;
  degisti: (yeni: Dilim | null) => void;
  gunSayisi?: number;
  ilkSaat?: number;
  sonSaat?: number;
  /** Test ve sunucu saati için; verilmezse cihaz saati. */
  simdi?: Date;
  teyitGoster?: boolean;
}) {
  const an = useMemo(() => simdi ?? new Date(), [simdi]);
  const gunler = useMemo(() => {
    const liste: Array<{ anahtar: string; etiket: string }> = [];
    for (let i = 0; i < gunSayisi; i++) {
      const d = new Date(an.getFullYear(), an.getMonth(), an.getDate() + i);
      const etiket = i === 0 ? 'Bugün' : i === 1 ? 'Yarın' : `${GUNLER[d.getDay()]} ${d.getDate()}`;
      liste.push({ anahtar: gunAnahtari(d), etiket });
    }
    return liste;
  }, [gunSayisi, an]);

  const bugun = gunler[0]?.anahtar ?? '';
  // Dilim seçilmeden gün seçilebilsin: seçili gün değerden, yoksa yerel durumdan.
  const [bosGun, setBosGun] = useState(bugun);
  const gun = deger ? deger.bas.slice(0, 10) : bosGun;

  const dilimler = useMemo(() => {
    const liste: Array<{ bas: number; bit: number }> = [];
    for (let s = ilkSaat; s + 2 <= sonSaat; s += 2) liste.push({ bas: s, bit: s + 2 });
    return liste;
  }, [ilkSaat, sonSaat]);

  const gunSec = (anahtar: string) => {
    setBosGun(anahtar);
    if (deger) {
      const bas = `${anahtar}${deger.bas.slice(10)}`;
      const saat = Number(deger.bit.slice(11, 13));
      // Bugüne dönülünce geçmiş dilim seçili kalmasın.
      if (anahtar === bugun && saat <= an.getHours()) degisti(null);
      else degisti({ ...deger, bas, bit: `${anahtar}${deger.bit.slice(10)}` });
    }
  };

  return (
    <div className="o-dilim">
      <CipSirasi etiket="Gün">
        {gunler.map((g) => (
          <Cip key={g.anahtar} secili={g.anahtar === gun} onClick={() => gunSec(g.anahtar)}>
            {g.etiket}
          </Cip>
        ))}
      </CipSirasi>
      <CipSirasi etiket="Saat aralığı">
        {dilimler.map((d) => {
          const bas = `${gun} ${iki(d.bas)}:00:00`;
          const bit = `${gun} ${iki(d.bit)}:00:00`;
          const gecmis = gun === bugun && d.bit <= an.getHours();
          const secili = deger?.bas === bas && deger?.bit === bit;
          return (
            <Cip
              key={d.bas}
              secili={secili}
              onClick={gecmis ? undefined : () => degisti(secili ? null : { bas, bit, teyitli: deger?.teyitli ?? false })}
              baslik={gecmis ? 'Bu saat geçti' : undefined}
            >
              <span className={gecmis ? 'o-gecmis' : undefined}>
                {iki(d.bas)}–{iki(d.bit)}
              </span>
            </Cip>
          );
        })}
      </CipSirasi>
      {teyitGoster ? (
        <label className="o-onay-kutusu">
          <input
            type="checkbox"
            checked={Boolean(deger?.teyitli)}
            disabled={!deger}
            onChange={(o) => deger && degisti({ ...deger, teyitli: o.target.checked })}
          />
          <span>Müşteriyle konuşuldu, saat teyitli</span>
        </label>
      ) : null}
    </div>
  );
}
