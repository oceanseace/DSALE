/**
 * HTML çağrı balonları — harita üstünde, bölge/mahalle etiketleri.
 *
 * Neden HTML: deck.gl TextLayer etiketleri şehir merkezinde üst üste biniyor (B1/B2/B3/B5
 * merkezleri 0,04–0,16° arayla). Burada kutular ekran uzayında itilir ve her birine
 * kendi boyunda bir bağlantı çizgisi (leader line) çıkar.
 *
 * Kadraj dışı kalan noktalar GİZLENMEZ: kutu ekran kenarına yaslanır ve yönü gösteren bir ok
 * (◂ / ▸) alır. "8 eşit bölge" karesinde B8 kadrajın 3.500 piksel sağındaydı ve sessizce
 * kayboluyordu — seyirci sekiz diyen başlığın altında yedi kutu sayıyordu.
 *
 * Konumlar React yeniden çizmeden, doğrudan `transform` ile yazılır: kamera 60 Hz aksa bile
 * React ağacı çalışmaz.
 */
import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef } from 'react';
import type { RefObject } from 'react';

import type { HaritaApi } from '../../map/HaritaSahnesi';
import type { LonLat } from '../../data/types';
import { boy, renk, u, uPx, yazi } from '../../ui/tema';

export interface CagriNoktasi {
  anahtar: string;
  konum: LonLat | [number, number, number];
  baslik: string;
  alt?: string;
  /** hex — kutu kenarı ve nokta rengi */
  renk: string;
  /** önce yerleşir ve hiç itilmez (ör. ofis feneri) — diğerleri ona göre kaçar */
  sabit?: boolean;
  /** daha küçük kutu: yalnız kod yazan bölge çipleri için */
  kucuk?: boolean;
  /** bu noktanın çizgi boyu (tasarım px) — verilmezse ortak `sap` */
  sap?: number;
}

export interface CagrilarApi {
  yerlestir: () => void;
}

export interface CagrilarProps {
  noktalar: CagriNoktasi[];
  haritaRef: RefObject<HaritaApi | null>;
  /** çizgi boyu (tasarım px) */
  sap?: number;
  boyut?: number;
  /** alt kenardan bırakılan pay (tasarım px) — lejant şeridi ve sahne noktaları oraya oturur */
  altPay?: number;
}

const Cagrilar = forwardRef<CagrilarApi, CagrilarProps>(function Cagrilar(
  { noktalar, haritaRef, sap = 64, boyut = boy.govde, altPay = 200 },
  ref,
) {
  const sarmalar = useRef(new Map<string, HTMLDivElement>());
  const saplar = useRef(new Map<string, HTMLDivElement>());
  const kutular = useRef(new Map<string, HTMLDivElement>());
  const noktacik = useRef(new Map<string, HTMLSpanElement>());
  const oklar = useRef(new Map<string, HTMLSpanElement>());
  /** kutu ölçüleri (ölçüm pahalı; anahtar başına bir kez okunur) */
  const olculer = useRef(new Map<string, { g: number; y: number }>());

  const yerlestir = useCallback(() => {
    const api = haritaRef.current;
    if (!api) return;
    const { width, height } = api.boyut();
    const pay = uPx(12); // kutular arası en küçük boşluk
    const yakin = uPx(330); // bu kadar yakın x'lerde çakışma çözülür
    const ustSinir = uPx(20); // kutunun üst kenarı bu çizginin altında kalmalı
    const altSap = uPx(46); // çevrilmiş kutunun çizgi boyu
    const kenarPay = uPx(20); // kırpılmış kutunun ekran kenarına uzaklığı

    interface Yerlesim {
      anahtar: string;
      x: number;
      y: number;
      /** kutunun ALT kenarının ekran y'si */
      kutuY: number;
      boy: number;
      genislik: number;
      sapPx: number;
      altta: boolean;
      gorunur: boolean;
      sabit: boolean;
      /** kadraj dışı: −1 solda, +1 sağda, 0 içeride */
      kirpik: -1 | 0 | 1;
    }

    const liste: Yerlesim[] = [];
    for (const n of noktalar) {
      const [hx, hy] = api.yansit(n.konum);
      const sapPx = uPx(n.sap ?? sap);
      let olcu = olculer.current.get(n.anahtar);
      if (!olcu || !olcu.y) {
        const el = kutular.current.get(n.anahtar);
        olcu = { g: el?.offsetWidth || uPx(220), y: el?.offsetHeight || uPx(84) };
        olculer.current.set(n.anahtar, olcu);
      }
      // ufkun ötesine düşen ya da kameranın arkasında kalan noktalar (saçma koordinat) gizlenir
      const saglam = Number.isFinite(hx) && Number.isFinite(hy) && Math.abs(hx) < width * 20 && Math.abs(hy) < height * 20;
      const enAz = olcu.g / 2 + kenarPay;
      let x = hx;
      let kirpik: -1 | 0 | 1 = 0;
      if (saglam) {
        if (hx < enAz) {
          x = enAz;
          kirpik = hx < -uPx(40) ? -1 : 0;
        } else if (hx > width - enAz) {
          x = width - enAz;
          kirpik = hx > width + uPx(40) ? 1 : 0;
        }
      }
      const y = saglam ? Math.min(Math.max(hy, ustSinir + olcu.y + sapPx), height - uPx(altPay)) : hy;
      liste.push({
        anahtar: n.anahtar,
        x,
        y,
        kutuY: y - sapPx,
        boy: olcu.y,
        genislik: olcu.g,
        sapPx,
        altta: false,
        gorunur: saglam,
        sabit: !!n.sabit,
        kirpik,
      });
    }

    const gorunurler = liste.filter((z) => z.gorunur);
    // 1. Ekranın tepesine sığmayan kutular çapanın ALTINA çevrilir (çizgi aşağı iner).
    for (const it of gorunurler) {
      if (it.kutuY - it.boy < ustSinir) {
        it.altta = true;
        it.kutuY = it.y + altSap + it.boy;
      }
    }
    // 2. Çakışma: sabit ve çevrilmiş kutular yerinde kalır, kalanlar yukarı itilir.
    const yerlesenler: Yerlesim[] = gorunurler.filter((z) => z.sabit || z.altta);
    for (const it of gorunurler.filter((z) => !z.sabit && !z.altta).sort((a, b) => b.kutuY - a.kutuY)) {
      // Tek geçiş yetmiyor: bir kutuyu yukarı ittikten sonra listede DAHA ÖNCE bakılmış bir
      // kutunun üstüne oturabiliyor (S10'da B2 ve B6 böyle ofis rozetinin altında kayboldu).
      // Hareket kalmayana kadar tekrarlanır.
      for (let tur = 0; tur < 8; tur++) {
        let hareket = false;
        for (const o of yerlesenler) {
          if (Math.abs(o.x - it.x) >= Math.min(yakin, (o.genislik + it.genislik) / 2 + pay)) continue;
          // bantlar kesişiyorsa `it` yukarı çıkar
          if (it.kutuY - it.boy < o.kutuY + pay && o.kutuY - o.boy < it.kutuY + pay) {
            it.kutuY = o.kutuY - o.boy - pay;
            hareket = true;
          }
        }
        if (!hareket) break;
      }
      yerlesenler.push(it);
    }

    for (const it of liste) {
      const sar = sarmalar.current.get(it.anahtar);
      if (!sar) continue;
      sar.style.transform = `translate3d(${Math.round(it.x)}px, ${Math.round(it.y)}px, 0)`;
      sar.style.opacity = it.gorunur ? '1' : '0';
      const sapEl = saplar.current.get(it.anahtar);
      const kutuEl = kutular.current.get(it.anahtar);
      const noktaEl = noktacik.current.get(it.anahtar);
      const okEl = oklar.current.get(it.anahtar);
      const alt = Math.round(it.y - it.kutuY); // kutunun çapaya göre yüksekliği (eksi = altta)
      const sapBoyu = Math.max(uPx(18), Math.abs(alt));
      // kırpılmış kutuda çapa yok: çizgi ve nokta yanıltıcı olurdu, yerine yön oku çıkar
      if (sapEl) {
        sapEl.style.height = `${sapBoyu}px`;
        sapEl.style.bottom = alt >= 0 ? '0px' : `${-sapBoyu}px`;
        sapEl.style.opacity = it.kirpik ? '0' : '1';
      }
      if (noktaEl) noktaEl.style.opacity = it.kirpik ? '0' : '1';
      if (kutuEl) kutuEl.style.bottom = `${alt}px`;
      if (okEl) {
        okEl.style.display = it.kirpik ? 'inline' : 'none';
        okEl.textContent = it.kirpik < 0 ? '◂ ' : ' ▸';
        okEl.style.order = it.kirpik < 0 ? '-1' : '1';
      }
    }
  }, [noktalar, haritaRef, sap, altPay]);

  useImperativeHandle(ref, () => ({ yerlestir }), [yerlestir]);

  useEffect(() => {
    olculer.current.clear();
    yerlestir();
    const zamanlar = [0, 80, 320, 900].map((ms) => window.setTimeout(yerlestir, ms));
    return () => zamanlar.forEach(clearTimeout);
  }, [yerlestir]);

  return (
    <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', overflow: 'hidden' }}>
      {noktalar.map((n, i) => {
        const b = n.kucuk ? boyut * 0.82 : boyut;
        return (
          <div
            key={n.anahtar}
            ref={(el) => {
              if (el) sarmalar.current.set(n.anahtar, el);
              else sarmalar.current.delete(n.anahtar);
            }}
            className={`dsale-cagri s-soluk s-g${Math.min(6, i + 1)}`}
            // sabit kutu (ofis rozeti) en üstte: başka bir çipin bağlantı çizgisi yazının
            // içinden geçmesin
            style={{ transition: 'opacity 240ms linear', zIndex: n.sabit ? 5 : 2 }}
          >
            {/* çapa noktası */}
            <span
              ref={(el) => {
                if (el) noktacik.current.set(n.anahtar, el);
                else noktacik.current.delete(n.anahtar);
              }}
              style={{
                position: 'absolute',
                left: u(-6),
                top: u(-6),
                width: u(12),
                height: u(12),
                borderRadius: '50%',
                background: n.renk,
                boxShadow: `0 0 ${u(18)} ${n.renk}`,
              }}
            />
            {/* bağlantı çizgisi */}
            <div
              ref={(el) => {
                if (el) saplar.current.set(n.anahtar, el);
                else saplar.current.delete(n.anahtar);
              }}
              style={{
                position: 'absolute',
                left: 0,
                bottom: 0,
                width: u(2),
                height: u(n.sap ?? sap),
                transform: 'translateX(-50%)',
                background: `linear-gradient(to top, ${n.renk}00, ${n.renk}cc)`,
              }}
            />
            {/* kutu */}
            <div
              ref={(el) => {
                if (el) kutular.current.set(n.anahtar, el);
                else kutular.current.delete(n.anahtar);
              }}
              style={{
                position: 'absolute',
                left: 0,
                bottom: u(n.sap ?? sap),
                transform: 'translateX(-50%)',
                whiteSpace: 'nowrap',
                background: 'rgba(4,9,20,0.88)',
                border: `1px solid ${n.renk}`,
                borderRadius: u(10),
                padding: n.kucuk ? `${u(5)} ${u(12)}` : `${u(8)} ${u(16)}`,
                boxShadow: `0 6px 26px rgba(0,0,0,0.6), 0 0 ${u(22)} ${n.renk}44`,
                backdropFilter: 'blur(8px)',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'baseline',
                  fontFamily: yazi.baslik,
                  fontWeight: 700,
                  fontSize: u(b),
                  letterSpacing: '0.02em',
                  color: renk.metin,
                  lineHeight: 1.1,
                }}
              >
                <span
                  ref={(el) => {
                    if (el) oklar.current.set(n.anahtar, el);
                    else oklar.current.delete(n.anahtar);
                  }}
                  style={{ display: 'none', color: n.renk }}
                />
                {n.baslik}
              </div>
              {n.alt && (
                <div
                  style={{
                    fontFamily: yazi.govde,
                    fontSize: u(b * 0.68),
                    color: n.renk,
                    fontVariantNumeric: 'tabular-nums',
                    marginTop: u(2),
                  }}
                >
                  {n.alt}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
});

export default Cagrilar;
