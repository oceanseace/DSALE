/**
 * "İlişkili iş farklı ekipte/atanmamış (N) — hepsini aynı ekibe ata" (TASKS araç çubuğu; Pano'dan
 * `#/yonetici/isler/suz/iliskili` ile de açılır). Perakende müşterinin açık işlerinden biri bir ekibe atanmışken
 * öbürleri başka ekipte ya da atanmamışsa grup listelenir; düğme hepsini çapa işin ekibine ve dilimine atar
 * (atama yazma yolu → BOSS). Askıdaki / altyapı bekleyen / yolda / sahadaki işler dokunulmaz. Her işin kendi kutusu
 * var (varsayılan işaretli; "onu atamayalım" diye kaldırılır); grup başlığındaki kutu grubun hepsini açar/kapatır.
 * Yalnız işaretliler gönderilir (`is_nolar`), düğmedeki sayı onları sayar.
 * Sunucu: `GET /api/isler/iliskili/uyumsuz` · `POST /api/isler/iliskili/hizala` (operasyon/v2/iliskili.py).
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { hataMetni, iliskiliHizala, iliskiliUyumsuz } from '../../../cekirdek/is/api';
import type { IliskiliUyumsuz } from '../../../cekirdek/is/tipler';
import { Dugme } from '../../../cekirdek/ortak/Ilkel';
import { Panel } from '../../../cekirdek/ortak/Panel';
import { dilimMetni, kisaAd } from './parcalar';
import { haricDegistir, topluIsaret } from './IliskiliSecim';

const YENILE_MS = 60_000;
const sayi = (n: number) => n.toLocaleString('tr-TR');

/** "Hepsini aynı ekibe ata"ya gidecek işler: bütün gruplardaki işlerden kutusu kaldırılmamış olanlar (sıra korunur). */
export function hizalaSecimi(veri: Pick<IliskiliUyumsuz, 'gruplar'> | null, haric: ReadonlySet<string>): string[] {
  const out: string[] = [];
  for (const g of veri?.gruplar ?? []) for (const x of g.isler) if (!haric.has(x.is_no) && !out.includes(x.is_no)) out.push(x.is_no);
  return out;
}

/** Uyumsuz ilişkili iş sayısı (dakikada bir ve `imza` değişince yeniden sorulur). */
export function useIliskiliUyumsuz(etkin: boolean, imza: unknown) {
  const [veri, setVeri] = useState<IliskiliUyumsuz | null>(null);
  const yenile = useCallback(() => {
    iliskiliUyumsuz()
      .then(setVeri)
      .catch(() => undefined);
  }, []);
  useEffect(() => {
    if (!etkin) return undefined;
    yenile();
    const t = window.setInterval(yenile, YENILE_MS);
    return () => window.clearInterval(t);
  }, [etkin, imza, yenile]);
  return { veri, yenile };
}

export function IliskiliHizalaPaneli({
  acik,
  kapat,
  veri,
  bitti,
}: {
  acik: boolean;
  kapat: () => void;
  veri: IliskiliUyumsuz | null;
  bitti: () => void;
}) {
  const [gidiyor, setGidiyor] = useState(false);
  const [sonuc, setSonuc] = useState<{ atanan: number; hatalar: Array<{ no: string; neden: string }> } | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  const [haric, setHaric] = useState<Set<string>>(() => new Set());
  useEffect(() => {
    if (acik) {
      setSonuc(null);
      setHata(null);
      setHaric(new Set());                       // her açılışta hepsi işaretli
    }
  }, [acik]);
  const secilen = useMemo(() => hizalaSecimi(veri, haric), [veri, haric]);
  const n = secilen.length;
  const toplam = veri?.is_sayisi ?? 0;
  const uygula = async () => {
    if (!secilen.length) return;               // boş liste sunucuda "hepsi" demek olurdu: hiç gönderilmez
    setGidiyor(true);
    setHata(null);
    try {
      const y = await iliskiliHizala(secilen);
      setSonuc({ atanan: y.atanan.length, hatalar: y.atlanan.map((a) => ({ no: a.is_no, neden: a.hata || a.kod })) });
      bitti();
    } catch (h) {
      setHata(hataMetni(h));
    } finally {
      setGidiyor(false);
    }
  };
  const alt = sonuc ? (
    <Dugme tur="birincil" genis onClick={kapat}>
      Kapat
    </Dugme>
  ) : (
    <>
      <Dugme tur="metin" onClick={kapat} disabled={gidiyor}>
        Vazgeç
      </Dugme>
      <Dugme tur="birincil" disabled={!n || gidiyor} onClick={() => void uygula()}>
        {gidiyor ? 'Atanıyor…' : `Hepsini aynı ekibe ata (${sayi(n)})`}
      </Dugme>
    </>
  );
  return (
    <Panel
      acik={acik}
      kapat={kapat}
      kilitli={gidiyor}
      baslik="İlişkili işler"
      altBaslik={`Farklı ekipte ya da atanmamış: ${sayi(toplam)} iş${n !== toplam ? ` · ${sayi(n)} işaretli` : ''}`}
      alt={alt}
    >
      <div className="ta-kok">
        {sonuc ? (
          <div className="ta-ozet" aria-live="polite">
            <div className="ta-sayilar">
              <span className="ta-sayi yesil">
                <b>{sayi(sonuc.atanan)}</b> ✓ atandı
              </span>
              {sonuc.hatalar.length ? (
                <span className="ta-sayi kirmizi">
                  <b>{sayi(sonuc.hatalar.length)}</b> hata
                </span>
              ) : null}
            </div>
            <p className="ta-not">Her atama BOSS’a da kendiliğinden yazılır (BOSS sekmesi açık olmalı).</p>
            {sonuc.hatalar.length ? (
              <ul className="ta-hatalar">
                {sonuc.hatalar.map((h) => (
                  <li key={h.no}>
                    <b>{h.no}</b> {h.neden}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : !veri ? (
          <p className="ta-not">Okunuyor…</p>
        ) : !veri.gruplar.length ? (
          <p className="ta-not">Farklı ekipte ya da atanmamış ilişkili iş yok.</p>
        ) : (
          <ul className="ta-iliskili-gruplar">
            {veri.gruplar.map((g) => (
              <li key={g.capa.is_no}>
                <label className="ta-baslik ta-iliskili-kutu">
                  <input
                    type="checkbox"
                    checked={topluIsaret(g.isler.map((x) => x.is_no), haric) === 'hepsi'}
                    ref={(el) => {
                      if (el) el.indeterminate = topluIsaret(g.isler.map((x) => x.is_no), haric) === 'kismi';
                    }}
                    onChange={(o) =>
                      setHaric((hr) => g.isler.reduce((acc, x) => haricDegistir(acc, x.is_no, o.target.checked), hr))
                    }
                    aria-label="Gruptaki hepsi"
                  />
                  <span>
                    {g.hedef.ad ? kisaAd(g.hedef.ad) : `#${g.hedef.teknik_id}`}
                    {g.hedef.randevu_bas && g.hedef.randevu_bit ? ` · ${dilimMetni(g.hedef.randevu_bas, g.hedef.randevu_bit)}` : ''}
                  </span>
                </label>
                <p className="ta-not">
                  <b>{g.capa.task_no}</b> {g.capa.task_adi} (çapa)
                </p>
                <ul className="ta-iliskili-liste">
                  {g.isler.map((x) => {
                    const isaretli = !haric.has(x.is_no);
                    return (
                      <li key={x.is_no} className={isaretli ? undefined : 'soluk'}>
                        <label className="ta-iliskili-is">
                          <input
                            type="checkbox"
                            checked={isaretli}
                            onChange={(o) => setHaric((hr) => haricDegistir(hr, x.is_no, o.target.checked))}
                            aria-label={`${x.task_no} ata`}
                          />
                          <span>
                            <b>{x.task_no}</b> {x.task_adi}
                            <span className="ta-not"> · {x.atanan ? `şu an ${x.atanan}` : 'atanmamış'}</span>
                          </span>
                        </label>
                      </li>
                    );
                  })}
                </ul>
              </li>
            ))}
          </ul>
        )}
        {hata ? <p className="ip-uyari kirmizi">{hata}</p> : null}
      </div>
    </Panel>
  );
}
