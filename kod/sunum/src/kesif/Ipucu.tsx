/** İmleci izleyen bina ipucu (hover). Dış depoya abonedir; harita yeniden çizilmez. */
import { useSyncExternalStore } from 'react';

import { binaBilgisi, sayi, temizAd } from '../data/selectors';
import type { Plan } from '../data/types';
import { boy, bosluk, renk, u, uPx, yazi } from '../ui/tema';
import { bolgeBul } from '../data/selectors';
import { OLCU } from './kameraHedefleri';
import { ipucuAbone, ipucuOku } from './ipucuDeposu';

export interface IpucuProps {
  plan: Plan;
  /** sağ çekmece açık mı — ipucu onun üstüne taşmasın */
  sagPanelAcik?: boolean;
}

export default function Ipucu({ plan, sagPanelAcik = false }: IpucuProps) {
  const d = useSyncExternalStore(ipucuAbone, ipucuOku, ipucuOku);
  if (d.i == null) return null;

  const b = binaBilgisi(d.i, plan);
  const bolge = bolgeBul(plan, b.bolge);
  const ad = temizAd(b.ad) || `Adsız bina · ${b.serial}`;
  const yer = [b.mahalle, b.ilce].filter(Boolean).join(' · ') + (b.il && b.il !== 'Bursa' ? ` · ${b.il}` : '');

  // imlecin 18 px sağ-altı; harita alanına taşarsa diğer tarafa geçer.
  // Sağ çekmece açıkken sınır ekran kenarı DEĞİL çekmecenin sol kenarıdır: ipucu "YERLEŞİM ALANI"
  // satırını ve fırsat dipnotunu örtüyor, dipnot da "…sat 0 sayılır" diye yarım okunuyordu.
  const gen = uPx(430);
  const yuk = uPx(190);
  const kayma = uPx(18);
  const sagSinir = window.innerWidth - (sagPanelAcik ? uPx(OLCU.sagGenislik + OLCU.kenar + 12) : 0);
  const x = d.x + kayma + gen > sagSinir ? Math.max(8, d.x - kayma - gen) : d.x + kayma;
  const y = d.y + kayma + yuk > window.innerHeight ? Math.max(8, d.y - kayma - yuk) : d.y + kayma;

  return (
    <div className="ks-ipucu" style={{ left: x, top: y }}>
      <div
        style={{
          fontFamily: yazi.baslik,
          fontWeight: 700,
          fontSize: u(boy.buyuk),
          color: renk.metin,
          lineHeight: 1.05,
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          maxWidth: u(400),
        }}
      >
        {ad}
      </div>
      <div style={{ fontSize: u(boy.kucuk), color: renk.metin2, marginTop: u(4) }}>{yer}</div>
      <div
        style={{
          fontSize: u(boy.govde),
          color: renk.metin,
          marginTop: u(bosluk.xs),
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        {b.resHp > 0 ? (
          <>
            {sayi(b.kat)} kat · {sayi(b.resHp)} hane · {sayi(b.firsat)} fırsat
          </>
        ) : (
          // res_hp = 0 olan binalar bozuk veri değil, konut kaydı olmayan binalardır (ticari/SOHO).
          // "19 kat · 0 hane · 0 fırsat" bozuk veri gibi okunuyordu.
          <>
            {sayi(b.kat)} kat · <span style={{ color: renk.metin3 }}>konut kaydı yok (ticari/SOHO)</span>
          </>
        )}
      </div>
      {bolge && (
        <div style={{ display: 'flex', alignItems: 'center', gap: u(10), marginTop: u(bosluk.xs) }}>
          <span
            style={{
              width: u(14),
              height: u(14),
              borderRadius: '50%',
              background: bolge.renk,
              boxShadow: `0 0 ${u(12)} ${bolge.renk}aa`,
            }}
          />
          <span style={{ fontSize: u(boy.kucuk), color: renk.metin2 }}>
            {bolge.kod} · {bolge.kisa_ad}
          </span>
        </div>
      )}
    </div>
  );
}
